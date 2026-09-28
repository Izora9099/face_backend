"""
Benchmark the face engine and calibrate FACE_MATCH_THRESHOLD.

    python manage.py evaluate_recognition                 # LFW (downloads ~180 MB once)
    python manage.py evaluate_recognition --dataset DIR   # your own DIR/<person>/*.jpg
    python manage.py evaluate_recognition --quick         # 2 LFW folds, for a fast check

Writes reports/recognition_eval.json, reports/recognition_eval.md and charts
(served to the admin UI at GET /api/recognition/report/).
"""

import json
import platform
import time
from itertools import combinations
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from core import evaluation as ev
from core import face_engine


class Command(BaseCommand):
    help = 'Evaluate recognition accuracy/speed and recommend a match threshold.'

    def add_arguments(self, parser):
        parser.add_argument('--dataset', type=Path, default=None,
                            help='Folder of <person>/<image> photos instead of LFW.')
        parser.add_argument('--data-dir', type=Path, default=settings.BASE_DIR / 'datasets',
                            help='Where LFW is downloaded and encodings cached.')
        parser.add_argument('--out', type=Path, default=settings.BASE_DIR / 'reports')
        parser.add_argument('--workers', type=int, default=None)
        parser.add_argument('--quick', action='store_true', help='Use only 2 of the 10 LFW folds.')

    def log(self, msg):
        self.stdout.write(msg)
        self.stdout.flush()

    def handle(self, *args, dataset, data_dir, out, workers, quick, **options):
        started = time.time()
        threshold = face_engine.get_threshold()

        if dataset:
            name, folds, people_paths, fallback = self._custom(dataset)
            cache_file = data_dir / f'encodings_{dataset.name}.npz'
        else:
            image_dir = ev.ensure_lfw(data_dir, self.log)
            folds = ev.read_pairs(data_dir / 'pairs.txt', image_dir)
            if quick:
                folds = folds[:2]
            name, fallback = 'LFW (Labeled Faces in the Wild), 10-fold pairs protocol', ev.LFW_FALLBACK_BOX
            people_paths = None
            cache_file = data_dir / 'encodings_lfw.npz'

        pair_paths = {p for fold in folds for a, b, _ in fold for p in (a, b)}
        cache = ev.encode_many(pair_paths, cache_file, fallback, workers, self.log)
        pairs, skipped = ev.pair_distances(folds, cache)
        if not len(pairs.distances):
            self.stderr.write('No usable pairs; nothing to evaluate.')
            return

        # ---- verification --------------------------------------------------
        self.log('Computing verification metrics ...')
        mean_acc, std_acc, fold_thresholds = ev.kfold_accuracy(pairs)
        roc = ev.roc(pairs)
        tar, far, frr = ev.rates_at(pairs, threshold)
        best_acc_threshold = float(np.median(fold_thresholds))
        secure_threshold = ev.threshold_for_far(pairs, 0.001)
        sweep = []
        for t in ev.THRESHOLDS[::4]:
            t_tar, t_far, t_frr = ev.rates_at(pairs, t)
            sweep.append({'threshold': float(t), 'accuracy': ev.accuracy_at(pairs, t),
                          'tar': t_tar, 'far': t_far, 'frr': t_frr})

        used = [cache[str(p)] for p in pair_paths if str(p) in cache]
        detection_rate = float(np.mean([d for _, d, _ in used])) if used else 0.0
        encode_ms = float(np.median([s for _, _, s in used]) * 1000) if used else 0.0

        # ---- identification (1:N) ------------------------------------------
        self.log('Computing 1:N identification ...')
        if people_paths is None:
            people_paths = {}
            for p in pair_paths:
                people_paths.setdefault(Path(p).parent.name, []).append(Path(p))
        people_vectors = {}
        for pid, paths in people_paths.items():
            vecs = [cache[str(p)][0] for p in sorted(paths) if str(p) in cache and cache[str(p)][0] is not None]
            if vecs:
                people_vectors[pid] = vecs
        ident = ev.identification(people_vectors, threshold)
        ident_best = ev.identification(people_vectors, best_acc_threshold)
        roster_curve = ev.identification_by_roster_size(
            people_vectors, sorted({threshold, secure_threshold}))

        self.log('Measuring match latency ...')
        latency = ev.latency_scaling()

        report = {
            'generated_at': timezone.now().isoformat(),
            'dataset': name,
            'engine': {
                'name': face_engine.ENGINE_NAME,
                'model': 'dlib ResNet-34 (face_recognition_model_v1), 128-d, HOG detector, 5-point alignment',
                'current_threshold': threshold,
            },
            'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                            'processor': platform.processor() or platform.machine()},
            'data': {
                'pairs_evaluated': int(len(pairs.distances)),
                'genuine_pairs': int(pairs.same.sum()),
                'impostor_pairs': int((~pairs.same).sum()),
                'pairs_skipped_unreadable': skipped,
                'images_encoded': len(used),
                'face_detection_rate': round(detection_rate, 4),
                'median_encode_ms': round(encode_ms, 1),
            },
            'verification': {
                'accuracy_kfold_mean': round(mean_acc, 4),
                'accuracy_kfold_std': round(std_acc, 4),
                'roc_auc': round(roc['auc'], 5),
                'eer': round(roc['eer'], 4),
                'eer_threshold': round(roc['eer_threshold'], 3),
                'at_current_threshold': {'threshold': threshold, 'accuracy': round(ev.accuracy_at(pairs, threshold), 4),
                                         'tar': round(tar, 4), 'far': round(far, 4), 'frr': round(frr, 4)},
                'genuine_distance': _describe(pairs.distances[pairs.same]),
                'impostor_distance': _describe(pairs.distances[~pairs.same]),
                'sweep': [{k: round(v, 4) for k, v in s.items()} for s in sweep],
            },
            'recommendation': {
                'balanced_threshold': round(best_acc_threshold, 3),
                'balanced_rates': dict(zip(('tar', 'far', 'frr'),
                                           (round(x, 4) for x in ev.rates_at(pairs, best_acc_threshold)))),
                'secure_threshold_far_0_1pct': round(secure_threshold, 3),
                'secure_rates': dict(zip(('tar', 'far', 'frr'),
                                         (round(x, 4) for x in ev.rates_at(pairs, secure_threshold)))),
                'note': ('Set FACE_MATCH_THRESHOLD in .env. Lower = fewer false accepts (impostors) '
                         'but more students needing a manual override.'),
            },
            'identification': {
                'at_current_threshold': ident,
                'at_balanced_threshold': ident_best,
                'by_roster_size': roster_curve,
                'note': ('Every extra enrolled face is another chance of a false match, so outsider '
                         'acceptance grows with the gallery. Matching is therefore scoped to the '
                         "session's course roster, and the threshold should tighten for large rosters."),
            },
            'scalability': {
                'match_latency': latency,
                'note': ('Matching is a single vectorised distance computation over the course roster; '
                         'enrolment needs no retraining, so cost grows linearly with enrolled faces.'),
            },
            'operational': _operational_stats(),
            'runtime_seconds': round(time.time() - started, 1),
        }

        out.mkdir(parents=True, exist_ok=True)
        report['charts'] = ev.save_charts(pairs, roc, sweep, latency, threshold, out, roster_curve)
        (out / 'recognition_eval.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        (out / 'recognition_eval.md').write_text(_markdown(report), encoding='utf-8')

        v, r = report['verification'], report['recommendation']
        self.stdout.write(self.style.SUCCESS(
            f"\nAccuracy {v['accuracy_kfold_mean']:.2%} +/- {v['accuracy_kfold_std']:.2%} | AUC {v['roc_auc']} | "
            f"EER {v['eer']:.2%}\nAt threshold {threshold}: FAR {far:.2%}, FRR {frr:.2%}\n"
            f"Recommended: balanced {r['balanced_threshold']}, secure (FAR<=0.1%) {r['secure_threshold_far_0_1pct']}\n"
            f"Report: {out / 'recognition_eval.md'}"))

    def _custom(self, root: Path):
        people = ev.folder_dataset(root)
        folds, rng = [[]], np.random.default_rng(0)
        names = list(people)
        for pid, paths in people.items():
            for a, b in combinations(paths, 2):
                folds[0].append((a, b, True))
        n_genuine = len(folds[0])
        for _ in range(max(n_genuine, 50)):
            i, j = rng.choice(len(names), 2, replace=False) if len(names) > 1 else (0, 0)
            if i == j:
                break
            folds[0].append((rng.choice(people[names[i]]), rng.choice(people[names[j]]), False))
        # Split into up to 5 folds so a threshold is still chosen out-of-sample.
        rows = folds[0]
        rng.shuffle(rows)
        k = min(5, max(1, len(rows) // 20))
        folds = [rows[i::k] for i in range(k)]
        return f'Custom dataset: {root}', folds, people, None


def _describe(x):
    if not len(x):
        return {}
    return {'mean': round(float(x.mean()), 4), 'std': round(float(x.std()), 4),
            'p5': round(float(np.percentile(x, 5)), 4), 'p95': round(float(np.percentile(x, 95)), 4)}


def _operational_stats():
    """How recognition behaves in real use (no biometric data involved)."""
    from core.models import AttendanceRecord, SessionCheckIn, Student

    checkins = SessionCheckIn.objects.all()
    total = checkins.count()
    recognised = checkins.filter(is_manual_override=False, recognition_confidence__isnull=False)
    manual = checkins.filter(is_manual_override=True).exclude(status='absent')
    conf = list(recognised.values_list('recognition_confidence', flat=True))
    return {
        'enrolled_students': Student.objects.exclude(face_images_count=0).count(),
        'total_students': Student.objects.count(),
        'session_checkins': total,
        'face_recognised_checkins': recognised.count(),
        'manual_overrides': manual.count(),
        'manual_override_rate': round(manual.count() / max(1, recognised.count() + manual.count()), 4),
        'confidence': _describe(np.array(conf)) if conf else {},
        'attendance_by_status': dict(
            AttendanceRecord.objects.values_list('status').annotate(n=Count('id')).values_list('status', 'n')),
    }


def _markdown(r):
    v, rec, d = r['verification'], r['recommendation'], r['data']
    cur = v['at_current_threshold']
    lines = [
        '# Face recognition evaluation', '',
        f"Generated {r['generated_at']} on {r['environment']['platform']}.", '',
        f"**Dataset:** {r['dataset']}  ",
        f"**Engine:** {r['engine']['model']}", '',
        '## Verification (1:1)', '',
        '| Metric | Value |', '|---|---|',
        f"| Pairs evaluated | {d['pairs_evaluated']} ({d['genuine_pairs']} genuine / {d['impostor_pairs']} impostor) |",
        f"| Face detection rate | {d['face_detection_rate']:.2%} |",
        f"| Accuracy (k-fold) | {v['accuracy_kfold_mean']:.2%} ± {v['accuracy_kfold_std']:.2%} |",
        f"| ROC AUC | {v['roc_auc']} |",
        f"| Equal error rate | {v['eer']:.2%} at distance {v['eer_threshold']} |",
        f"| At current threshold {cur['threshold']} | accuracy {cur['accuracy']:.2%}, FAR {cur['far']:.2%}, FRR {cur['frr']:.2%} |",
        f"| Median encode time | {d['median_encode_ms']} ms / image |", '',
        '## Threshold recommendation', '',
        f"- Balanced (max accuracy): **{rec['balanced_threshold']}** — FAR {rec['balanced_rates']['far']:.2%}, "
        f"FRR {rec['balanced_rates']['frr']:.2%}",
        f"- Secure (FAR ≤ 0.1%): **{rec['secure_threshold_far_0_1pct']}** — FAR {rec['secure_rates']['far']:.2%}, "
        f"FRR {rec['secure_rates']['frr']:.2%}",
        f"- {rec['note']}", '',
    ]
    ident = r['identification'].get('at_current_threshold')
    if ident:
        lines += [
            '## Identification (1:N)', '',
            f"Gallery of {ident['gallery_size']} identities, {ident['genuine_probes']} genuine probes"
            + (f", {ident.get('impostor_probes')} impostor probes." if ident.get('impostor_probes') else '.'), '',
            '| Metric | Value |', '|---|---|',
            f"| Rank-1 accuracy | {ident['rank1_accuracy']:.2%} |",
            f"| Correctly identified and accepted (DIR) | {ident['dir']:.2%} |",
            f"| Rejected (needs manual override) | {ident['false_reject_rate']:.2%} |",
            f"| Misidentified and accepted | {ident['misidentification_rate']:.2%} |",
        ]
        if 'fpir' in ident:
            lines.append(f"| Impostors wrongly accepted (FPIR) | {ident['fpir']:.2%} |")
        lines.append('')
    curve = r['identification'].get('by_roster_size') or []
    if curve:
        lines += ['### Error vs roster size', '',
                  f"Averaged over random rosters. {r['identification']['note']}", '',
                  '| Roster size | Threshold | Rank-1 | Correct + accepted | Misidentified | Outsider accepted |',
                  '|---|---|---|---|---|---|']
        lines += [f"| {c['roster_size']} | {c['threshold']:g} | {c['rank1']:.2%} | {c['dir']:.2%} | "
                  f"{c['misid']:.2%} | {c['fpir']:.2%} |" for c in curve]
        lines.append('')
    lines += ['## Scalability', '', '| Enrolled faces compared | Match time (median) |', '|---|---|']
    lines += [f"| {x['gallery_size']:,} | {x['median_ms']} ms |" for x in r['scalability']['match_latency']]
    lines += ['', r['scalability']['note'], '']
    op = r['operational']
    lines += ['## Operational statistics (this deployment)', '',
              f"- Students with an enrolled face: {op['enrolled_students']} / {op['total_students']}",
              f"- Session check-ins: {op['session_checkins']} (recognised {op['face_recognised_checkins']}, "
              f"manual overrides {op['manual_overrides']}, override rate {op['manual_override_rate']:.2%})",
              f"- Attendance by status: {op['attendance_by_status']}", '']
    if r.get('charts'):
        lines += ['## Charts', ''] + [f'![{c}]({c})' for c in r['charts']] + ['']
    return '\n'.join(lines)
