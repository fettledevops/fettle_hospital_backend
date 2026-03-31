import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='DermatologyPatient',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'dermatology_patients'},
        ),
        migrations.CreateModel(
            name='GlobalConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=255, unique=True)),
                ('value', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'global_config'},
        ),
        migrations.CreateModel(
            name='DermatologyThread',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(default='Consultation', max_length=255)),
                ('mode', models.CharField(
                    choices=[
                        ('general_education', 'General Education'),
                        ('post_payment_intake', 'Post Payment Intake'),
                        ('dermatologist_review', 'Dermatologist Review'),
                        ('final_output', 'Final Output'),
                    ],
                    default='general_education',
                    max_length=50,
                )),
                ('payment_status', models.CharField(
                    choices=[('unpaid', 'Unpaid'), ('paid', 'Paid')],
                    default='unpaid',
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[('active', 'Active'), ('completed', 'Completed')],
                    default='active',
                    max_length=20,
                )),
                ('conversation', models.JSONField(default=list)),
                ('intake_data', models.JSONField(blank=True, null=True)),
                ('draft_response', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='threads',
                    to='chatbot.dermatologypatient',
                )),
            ],
            options={
                'db_table': 'dermatology_threads',
                'ordering': ['-created_at'],
            },
        ),
    ]
