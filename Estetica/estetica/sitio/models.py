# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Cita(models.Model):
    id_cita = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey('Usuario', models.DB_CASCADE, db_column='id_usuario', blank=True, null=True)
    id_servicio = models.ForeignKey('Servicio', models.DB_CASCADE, db_column='id_servicio', blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)
    hora_inicio = models.TimeField(blank=True, null=True)
    hora_fin = models.TimeField(blank=True, null=True)
    estado = models.CharField(max_length=9, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cita'


class Horario(models.Model):
    id_horario = models.AutoField(primary_key=True)
    dia_semana = models.CharField(max_length=10, blank=True, null=True)
    apertura = models.TimeField(blank=True, null=True)
    cierre = models.TimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'horario'


class Servicio(models.Model):
    id_servicio = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, blank=True, null=True)
    duracion_min = models.IntegerField(blank=True, null=True)
    precio = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'servicio'


class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, blank=True, null=True)
    correo = models.CharField(max_length=100, blank=True, null=True)
    psswd = models.CharField(max_length=50, blank=True, null=True)
    rol = models.CharField(max_length=13, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usuario'