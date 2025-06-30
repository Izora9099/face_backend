# Create this file as: core/migrations/0005_add_timetable_models.py
# Run: python manage.py makemigrations and python manage.py migrate

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_adminuser_options_alter_level_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TimeSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.IntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('duration_minutes', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['day_of_week', 'start_time'],
            },
        ),
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('capacity', models.IntegerField()),
                ('building', models.CharField(blank=True, max_length=100)),
                ('floor', models.CharField(blank=True, max_length=20)),
                ('equipment', models.JSONField(blank=True, default=list)),
                ('is_available', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['building', 'name'],
            },
        ),
        migrations.CreateModel(
            name='TimetableEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('academic_year', models.CharField(default='2024-2025', max_length=20)),
                ('semester', models.IntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(3)])),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_entries', to='core.course')),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_entries', to='core.room')),
                ('teacher', models.ForeignKey(limit_choices_to={'role': 'teacher'}, on_delete=django.db.models.deletion.CASCADE, related_name='timetable_entries', to=settings.AUTH_USER_MODEL)),
                ('time_slot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_entries', to='core.timeslot')),
            ],
            options={
                'ordering': ['time_slot__day_of_week', 'time_slot__start_time'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='timeslot',
            unique_together={('day_of_week', 'start_time')},
        ),
        migrations.AlterUniqueTogether(
            name='timetableentry',
            unique_together={('time_slot', 'room'), ('time_slot', 'teacher')},
        ),
        migrations.AddIndex(
            model_name='timetableentry',
            index=models.Index(fields=['academic_year', 'semester'], name='core_timetab_academi_c8b2a1_idx'),
        ),
        migrations.AddIndex(
            model_name='timetableentry',
            index=models.Index(fields=['teacher', 'time_slot'], name='core_timetab_teacher_b7c4d3_idx'),
        ),
        migrations.AddIndex(
            model_name='timetableentry',
            index=models.Index(fields=['course', 'time_slot'], name='core_timetab_course__e9f1a2_idx'),
        ),
    ]