# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0876_graphtimeframe'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='graphtimeframe',
            options={'ordering': ('-relative_to_now', 'timeframe_offset', 'seconds')},
        ),
        migrations.AlterField(
            model_name='mvstructentry',
            name='type_instance',
            field=models.CharField(default=b'', max_length=255),
        ),
    ]
