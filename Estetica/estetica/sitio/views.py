from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Cita, Servicio, Usuario

DURACION_POR_DEFECTO = 60
ESTADO_PENDIENTE = 'pendiente'
ESTADO_CANCELADA = 'cancelada'
ROL_ADMINISTRADOR = 'administrador'


def _usuario_en_sesion(request):
    """Devuelve el usuario guardado en la sesión o None."""
    return Usuario.objects.filter(pk=request.session.get('usuario_id')).first()


def index(request):
    servicios_destacados = Servicio.objects.all().order_by('nombre')[:3]

    context = {
        'servicios_destacados': servicios_destacados,
    }

    return render(request, 'sitio/index.html', context)


def servicios(request):
    listado_servicios = Servicio.objects.all().order_by('nombre')

    context = {
        'servicios': listado_servicios
    }

    return render(request, 'sitio/servicios.html', context)


def listado_citas(request):
    """Panel de citas registradas, solo para el rol administrador."""
    usuario = _usuario_en_sesion(request)

    if usuario is None:
        return redirect(f"{reverse('login')}?next={reverse('citas')}")

    if (usuario.rol or '').strip().lower() != ROL_ADMINISTRADOR:
        messages.error(request, 'Solo el personal administrador puede consultar las citas registradas.')
        return redirect('index')

    citas = (
        Cita.objects
        .select_related('id_usuario', 'id_servicio')
        .order_by('-fecha', '-hora_inicio')
    )

    context = {
        'citas': citas,
        'total_citas': citas.count(),
        'citas_pendientes': citas.filter(estado=ESTADO_PENDIENTE).count(),
        'citas_hoy': citas.filter(fecha=date.today()).count(),
        'usuario': usuario,
    }

    return render(request, 'sitio/citas.html', context)


def iniciar_sesion(request):
    if request.session.get('usuario_id'):
        return redirect('index')

    siguiente = request.POST.get('next') or request.GET.get('next') or ''
    correo = ''

    if request.method == 'POST':
        correo = (request.POST.get('correo') or '').strip()
        psswd = request.POST.get('psswd') or ''

        if not correo or not psswd:
            messages.error(request, 'Captura tu correo y tu contraseña.')
        else:
            # La tabla `usuario` guarda la contraseña en texto plano.
            usuario = Usuario.objects.filter(correo__iexact=correo, psswd=psswd).first()

            if usuario is None:
                messages.error(request, 'El correo o la contraseña no son correctos.')
            else:
                request.session.flush()
                request.session['usuario_id'] = usuario.id_usuario
                request.session['usuario_nombre'] = usuario.nombre or usuario.correo
                request.session['usuario_rol'] = usuario.rol or 'cliente'

                if siguiente and url_has_allowed_host_and_scheme(
                    siguiente, allowed_hosts={request.get_host()}
                ):
                    return redirect(siguiente)

                return redirect('index')

    context = {
        'correo': correo,
        'siguiente': siguiente,
    }

    return render(request, 'sitio/login.html', context)


def cerrar_sesion(request):
    request.session.flush()
    messages.success(request, 'Cerraste sesión correctamente.')

    return redirect('index')


def formulario(request):
    usuario = _usuario_en_sesion(request)

    if usuario is None:
        return redirect(f"{reverse('login')}?next={reverse('formulario')}")

    listado_servicios = Servicio.objects.all().order_by('nombre')
    datos = {'id_servicio': '', 'fecha': '', 'hora_inicio': ''}
    errores = []

    if request.method == 'POST':
        datos = {
            'id_servicio': (request.POST.get('id_servicio') or '').strip(),
            'fecha': (request.POST.get('fecha') or '').strip(),
            'hora_inicio': (request.POST.get('hora_inicio') or '').strip(),
        }

        servicio = None
        if datos['id_servicio'].isdigit():
            servicio = listado_servicios.filter(pk=int(datos['id_servicio'])).first()

        if servicio is None:
            errores.append('Selecciona el servicio que deseas.')

        try:
            fecha_cita = date.fromisoformat(datos['fecha'])
        except ValueError:
            fecha_cita = None
            errores.append('Indica una fecha válida.')

        try:
            hora_cita = time.fromisoformat(datos['hora_inicio'])
        except ValueError:
            hora_cita = None
            errores.append('Indica una hora válida.')

        if fecha_cita and fecha_cita < date.today():
            errores.append('La fecha de la cita no puede estar en el pasado.')

        if fecha_cita == date.today() and hora_cita and hora_cita < datetime.now().time():
            errores.append('Esa hora ya pasó. Elige una hora posterior a la actual.')

        fin = None
        if servicio and fecha_cita and hora_cita:
            inicio = datetime.combine(fecha_cita, hora_cita)
            fin = inicio + timedelta(minutes=servicio.duracion_min or DURACION_POR_DEFECTO)

            if fin.date() != fecha_cita:
                fin = None
                errores.append(
                    'La cita terminaría después de la medianoche, elige una hora más temprana.'
                )
            elif Cita.objects.filter(
                fecha=fecha_cita,
                hora_inicio__lt=fin.time(),
                hora_fin__gt=hora_cita,
            ).exclude(estado=ESTADO_CANCELADA).exists():
                errores.append('Ese horario ya está ocupado. Elige otra hora.')

        if servicio and fecha_cita and hora_cita and fin and not errores:
            Cita.objects.create(
                id_usuario=usuario,
                id_servicio=servicio,
                fecha=fecha_cita,
                hora_inicio=hora_cita,
                hora_fin=fin.time(),
                estado=ESTADO_PENDIENTE,
            )

            messages.success(
                request,
                f'Tu cita de {servicio.nombre} quedó agendada para el '
                f'{fecha_cita:%d/%m/%Y} a las {hora_cita:%H:%M}.'
            )

            return redirect('formulario')

    context = {
        'servicios': listado_servicios,
        'datos': datos,
        'errores': errores,
        'usuario': usuario,
        'hoy': date.today(),
    }

    return render(request, 'sitio/formulario.html', context)
