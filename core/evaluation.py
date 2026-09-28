"""
Recognition benchmark: verification (LFW 10-fold protocol), threshold
calibration, 1:N identification and match-latency scaling.

Kept free of Django model imports so encoding can run in worker processes.
"""

from __future__ import annotations

import os
import tarfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Mirrors used by scikit-learn's fetch_lfw_* (the original UMass host is often down).
LFW_ARCHIVE_URL = 'https://ndownloader.figshare.com/files/5976018'   # lfw.tgz (~173 MB)
LFW_PAIRS_URL = 'https://ndownloader.figshare.com/files/5976006'     # pairs.txt (10 folds x 600)
LFW_FALLBACK_BOX = (70, 70, 180, 180)  # faces in LFW are roughly centred in 250x250 images


# --------------------------------------------------------------------------
# Dataset
# --------------------------------------------------------------------------
def _download(url, dest: Path, log):
    log(f'Downloading {url} -> {dest}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.part')
    with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, 'wb') as fh:
        total = int(resp.headers.get('Content-Length') or 0)
        done = 0
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
            done += len(chunk)
            if total and done % (20 << 20) < (1 << 20):
                log(f'  {done >> 20} / {total >> 20} MB')
    tmp.replace(dest)


def ensure_lfw(root: Path, log=print) -> Path:
    """Download and extract LFW into root/lfw if missing. Returns the image dir."""
    image_dir = root / 'lfw'
    if not image_dir.exists():
        archive = root / 'lfw.tgz'
        if not archive.exists():
            _download(LFW_ARCHIVE_URL, archive, log)
        log('Extracting LFW ...')
        with tarfile.open(archive) as tar:
            tar.extractall(root, filter='data')
    if not (root / 'pairs.txt').exists():
        _download(LFW_PAIRS_URL, root / 'pairs.txt', log)
    return image_dir


def lfw_path(image_dir: Path, name: str, idx: int) -> Path:
    return image_dir / name / f'{name}_{int(idx):04d}.jpg'


def read_pairs(pairs_file: Path, image_dir: Path):
    """Returns folds: list of lists of (path_a, path_b, same: bool)."""
    lines = pairs_file.read_text().strip().splitlines()
    n_folds, n_per = map(int, lines[0].split())
    rows = [line.split('\t') for line in lines[1:]]
    folds = []
    for f in range(n_folds):
        chunk = rows[f * 2 * n_per:(f + 1) * 2 * n_per]
        fold = []
        for r in chunk:
            if len(r) == 3:
                fold.append((lfw_path(image_dir, r[0], r[1]), lfw_path(image_dir, r[0], r[2]), True))
            else:
                fold.append((lfw_path(image_dir, r[0], r[1]), lfw_path(image_dir, r[2], r[3]), False))
        folds.append(fold)
    return folds


def folder_dataset(root: Path):
    """A custom dataset laid out as root/<person>/<image>.jpg -> {person: [paths]}."""
    people = {}
    for person_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        images = sorted(q for q in person_dir.iterdir() if q.suffix.lower() in ('.jpg', '.jpeg', '.png'))
        if images:
            people[person_dir.name] = images
    return people


# --------------------------------------------------------------------------
# Encoding (runs in worker processes)
# --------------------------------------------------------------------------
def encode_path(path_str: str, fallback_box=None):
    """
    -> (path, vector|None, detected: bool, seconds). Uses the production
    engine's models; if no face is found and a fallback box is given, encodes
    that region instead (standard practice for pre-aligned sets like LFW).
    """
    import dlib
    from PIL import Image

    from core import face_engine

    started = time.perf_counter()
    try:
        img = np.asarray(Image.open(path_str).convert('RGB'))
    except OSError:
        return path_str, None, False, 0.0
    m = face_engine._models()
    rects = face_engine._detect(img, 'hog')
    detected = bool(rects)
    if rects:
        rect = max(rects, key=lambda r: r.width() * r.height())
    elif fallback_box:
        rect = dlib.rectangle(*fallback_box)
    else:
        return path_str, None, False, time.perf_counter() - started
    vec = np.asarray(m['encoder'].compute_face_descriptor(img, m['pose'](img, rect), 1), dtype=np.float64)
    return path_str, vec, detected, time.perf_counter() - started


def encode_many(paths, cache_file: Path, fallback_box=None, workers=None, log=print):
    """Encode unique paths with a process pool, caching results in an .npz."""
    cache = {}
    if cache_file.exists():
        data = np.load(cache_file, allow_pickle=False)
        for p, v, d, s in zip(data['paths'], data['vectors'], data['detected'], data['seconds']):
            cache[str(p)] = (v if not np.isnan(v[0]) else None, bool(d), float(s))

    todo = sorted({str(p) for p in paths} - set(cache))
    if todo:
        from concurrent.futures import ProcessPoolExecutor

        workers = workers or max(1, (os.cpu_count() or 2) - 1)
        log(f'Encoding {len(todo)} images with {workers} workers (cached: {len(cache)}) ...')
        started = time.time()
        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init) as pool:
            for i, (p, v, d, s) in enumerate(pool.map(encode_path, todo, [fallback_box] * len(todo),
                                                     chunksize=16), start=1):
                cache[p] = (v, d, s)
                if i % 500 == 0 or i == len(todo):
                    rate = i / (time.time() - started)
                    log(f'  {i}/{len(todo)} ({rate:.1f} img/s)')
        _save_cache(cache, cache_file)
    return cache


def _worker_init():
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_backend.settings')
    django.setup()


def _save_cache(cache, cache_file: Path):
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    paths = list(cache)
    vectors = np.array([cache[p][0] if cache[p][0] is not None else np.full(128, np.nan) for p in paths])
    np.savez_compressed(cache_file, paths=np.array(paths), vectors=vectors,
                        detected=np.array([cache[p][1] for p in paths]),
                        seconds=np.array([cache[p][2] for p in paths]))


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
THRESHOLDS = np.round(np.arange(0.20, 1.001, 0.005), 3)


@dataclass
class Pairs:
    distances: np.ndarray
    same: np.ndarray
    fold: np.ndarray


def pair_distances(folds, cache) -> tuple[Pairs, int]:
    d, same, fold_ids, skipped = [], [], [], 0
    for f, fold in enumerate(folds):
        for a, b, s in fold:
            va, vb = cache.get(str(a), (None,))[0], cache.get(str(b), (None,))[0]
            if va is None or vb is None:
                skipped += 1
                continue
            d.append(float(np.linalg.norm(va - vb)))
            same.append(s)
            fold_ids.append(f)
    return Pairs(np.array(d), np.array(same), np.array(fold_ids)), skipped


def accuracy_at(p: Pairs, t, mask=None):
    mask = np.ones_like(p.same, bool) if mask is None else mask
    pred = p.distances[mask] <= t
    return float((pred == p.same[mask]).mean())


def rates_at(p: Pairs, t):
    """TAR (genuine accepted), FAR (impostor accepted), FRR = 1 - TAR."""
    gen, imp = p.distances[p.same], p.distances[~p.same]
    tar = float((gen <= t).mean()) if len(gen) else 0.0
    far = float((imp <= t).mean()) if len(imp) else 0.0
    return tar, far, 1 - tar


def kfold_accuracy(p: Pairs):
    """LFW protocol: pick the best threshold on 9 folds, test on the 10th."""
    accs, chosen = [], []
    for f in np.unique(p.fold):
        train, test = p.fold != f, p.fold == f
        best = max(THRESHOLDS, key=lambda t: accuracy_at(p, t, train))
        chosen.append(float(best))
        accs.append(accuracy_at(p, best, test))
    return float(np.mean(accs)), float(np.std(accs)), chosen


def roc(p: Pairs):
    grid = np.linspace(0, 1.6, 641)
    points = [rates_at(p, t)[:2] for t in grid]
    tar = np.array([x[0] for x in points])
    far = np.array([x[1] for x in points])
    auc = float(np.trapezoid(tar, far)) if hasattr(np, 'trapezoid') else float(np.trapz(tar, far))
    frr = 1 - tar
    i = int(np.argmin(np.abs(far - frr)))
    return {'thresholds': grid, 'tar': tar, 'far': far, 'auc': auc,
            'eer': float((far[i] + frr[i]) / 2), 'eer_threshold': float(grid[i])}


def threshold_for_far(p: Pairs, target_far):
    """Largest threshold whose FAR does not exceed target_far."""
    ok = [t for t in THRESHOLDS if rates_at(p, t)[1] <= target_far]
    return float(max(ok)) if ok else float(THRESHOLDS[0])


def identification(people_vectors: dict, threshold: float, rng_seed=0):
    """
    Closed/open-set 1:N identification.
    Gallery: first image of each identity with >= 2 images. Genuine probes:
    their other images. Impostor probes: identities with a single image
    (not in the gallery) - they should be rejected.
    """
    rng = np.random.default_rng(rng_seed)
    gallery_ids, gallery, probes, probe_ids, impostors = [], [], [], [], []
    for pid, vecs in people_vectors.items():
        if len(vecs) >= 2:
            gallery_ids.append(pid)
            gallery.append(vecs[0])
            for v in vecs[1:]:
                probes.append(v)
                probe_ids.append(pid)
        else:
            impostors.append(vecs[0])
    if not gallery:
        return None
    G = np.vstack(gallery)
    gallery_ids = np.array(gallery_ids)

    def nearest(vs):
        vs = np.vstack(vs)
        # ||a-b||^2 = |a|^2 + |b|^2 - 2ab, batched
        d2 = (vs ** 2).sum(1)[:, None] + (G ** 2).sum(1)[None, :] - 2 * vs @ G.T
        idx = d2.argmin(1)
        return idx, np.sqrt(np.maximum(d2[np.arange(len(vs)), idx], 0))

    idx, dist = nearest(probes)
    correct = gallery_ids[idx] == np.array(probe_ids)
    accepted = dist <= threshold
    result = {
        'gallery_size': int(len(G)),
        'genuine_probes': int(len(probes)),
        'rank1_accuracy': float(correct.mean()),
        'dir': float((correct & accepted).mean()),  # detected and correctly identified
        'false_reject_rate': float((~accepted).mean()),
        'misidentification_rate': float((~correct & accepted).mean()),
    }
    if impostors:
        _, idist = nearest(impostors)
        result['impostor_probes'] = int(len(impostors))
        result['fpir'] = float((idist <= threshold).mean())  # impostor wrongly accepted
    return result


def latency_scaling(dim=128, sizes=(10, 100, 1_000, 10_000, 100_000), repeats=50, rng_seed=0):
    """Median time of one face_engine.match() call as the candidate set grows."""
    from core import face_engine

    rng = np.random.default_rng(rng_seed)
    out = []
    for n in sizes:
        cands = [(i, v) for i, v in enumerate(rng.normal(0, 0.1, (n, dim)))]
        probe = rng.normal(0, 0.1, dim)
        times = []
        for _ in range(repeats):
            t = time.perf_counter()
            face_engine.match(probe, cands, threshold=0.6)
            times.append(time.perf_counter() - t)
        out.append({'gallery_size': n, 'median_ms': round(float(np.median(times)) * 1000, 3)})
    return out


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def save_charts(p: Pairs, roc_data, sweep, latency, threshold, out_dir: Path):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    files = []
    blue, orange, grey = '#2563eb', '#ea580c', '#6b7280'

    fig, ax = plt.subplots(figsize=(6.4, 4))
    bins = np.linspace(0, 1.4, 71)
    ax.hist(p.distances[p.same], bins=bins, alpha=.75, color=blue, label='Same person')
    ax.hist(p.distances[~p.same], bins=bins, alpha=.75, color=orange, label='Different people')
    ax.axvline(threshold, color=grey, ls='--', lw=1.2, label=f'Threshold {threshold:.2f}')
    ax.set(xlabel='Face distance (128-d Euclidean)', ylabel='Pairs', title='LFW pair distance distributions')
    ax.legend(frameon=False)
    files.append(_save(fig, out_dir / 'distance_histogram.png'))

    fig, ax = plt.subplots(figsize=(5, 4.6))
    ax.plot(roc_data['far'], roc_data['tar'], color=blue, lw=2, label=f"AUC = {roc_data['auc']:.4f}")
    ax.set(xscale='log', xlim=(1e-4, 1), ylim=(0.8, 1.001), xlabel='False accept rate (log)',
           ylabel='True accept rate', title='ROC (LFW verification)')
    ax.grid(alpha=.3)
    ax.legend(frameon=False, loc='lower right')
    files.append(_save(fig, out_dir / 'roc.png'))

    fig, ax = plt.subplots(figsize=(6.4, 4))
    ts = [s['threshold'] for s in sweep]
    ax.plot(ts, [s['accuracy'] for s in sweep], color=blue, lw=2, label='Accuracy')
    ax.plot(ts, [s['far'] for s in sweep], color=orange, lw=1.5, label='FAR')
    ax.plot(ts, [s['frr'] for s in sweep], color=grey, lw=1.5, label='FRR')
    ax.axvline(threshold, color='k', ls='--', lw=1)
    ax.set(xlabel='Threshold', ylabel='Rate', title='Operating point vs threshold', ylim=(0, 1))
    ax.grid(alpha=.3)
    ax.legend(frameon=False)
    files.append(_save(fig, out_dir / 'threshold_sweep.png'))

    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.plot([x['gallery_size'] for x in latency], [x['median_ms'] for x in latency], 'o-', color=blue, lw=2)
    ax.set(xscale='log', yscale='log', xlabel='Enrolled faces compared (N)', ylabel='Match time (ms, median)',
           title='1:N match latency')
    ax.grid(alpha=.3, which='both')
    files.append(_save(fig, out_dir / 'match_latency.png'))
    return files


def _save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return path.name
