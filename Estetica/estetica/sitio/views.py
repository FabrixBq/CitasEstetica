from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Cita, Horario, Servicio, Usuario

DURACION_POR_DEFECTO = 60
MARGEN_CIERRE_MIN = 10
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
ESTADO_PENDIENTE = 'pendiente'
ESTADO_LISTA = 'lista'
ESTADO_CANCELADA = 'cancelada'
ROL_ADMINISTRADOR = 'administrador'


def _usuario_en_sesion(request):
    """Devuelve el usuario guardado en la sesión o None."""
    return Usuario.objects.filter(pk=request.session.get('usuario_id')).first()


def _es_administrador(usuario):
    return (usuario.rol or '').strip().lower() == ROL_ADMINISTRADOR


def _panel_de_citas(usuario):
    """Nombre de la ruta del panel que le corresponde al usuario."""
    return 'citas' if _es_administrador(usuario) else 'mis_citas'


def _cita_cancelada(cita):
    return (cita.estado or '').strip().lower() == ESTADO_CANCELADA


def _hora_cierre(fecha):
    """Hora de cierre del salón para la fecha indicada, o None si no hay horario."""
    horario = Horario.objects.filter(dia_semana__iexact=DIAS_SEMANA[fecha.weekday()]).first()

    return horario.cierre if horario else None


def _marcar_citas_atendidas():
    """Pasa de 'pendiente' a 'lista' las citas cuyo horario ya terminó."""
    hoy = date.today()
    ahora = datetime.now().time()

    return (
        Cita.objects
        .filter(estado=ESTADO_PENDIENTE)
        .filter(Q(fecha__lt=hoy) | Q(fecha=hoy, hora_fin__lte=ahora))
        .update(estado=ESTADO_LISTA)
    )


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

    if not _es_administrador(usuario):
        messages.error(request, 'Solo el personal administrador puede consultar las citas registradas.')
        return redirect('index')

    _marcar_citas_atendidas()

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
        'citas_canceladas': citas.filter(estado=ESTADO_CANCELADA).count(),
        'usuario': usuario,
    }

    return render(request, 'sitio/citas.html', context)


def mis_citas(request):
    """Citas agendadas por el cliente en sesión, con opción de cancelarlas."""
    usuario = _usuario_en_sesion(request)

    if usuario is None:
        return redirect(f"{reverse('login')}?next={reverse('mis_citas')}")

    if _es_administrador(usuario):
        return redirect('citas')

    _marcar_citas_atendidas()

    citas = (
        Cita.objects
        .filter(id_usuario=usuario)
        .select_related('id_servicio')
        .order_by('fecha', 'hora_inicio')
    )

    hoy = date.today()
    citas_proximas = []
    citas_anteriores = []

    for cita in citas:
        finalizada = _cita_cancelada(cita) or (cita.estado or '').strip().lower() == ESTADO_LISTA

        if not finalizada and cita.fecha and cita.fecha >= hoy:
            citas_proximas.append(cita)
        else:
            citas_anteriores.append(cita)

    citas_anteriores.reverse()

    context = {
        'usuario': usuario,
        'citas_proximas': citas_proximas,
        'citas_anteriores': citas_anteriores,
        'total_citas': len(citas_proximas) + len(citas_anteriores),
        'citas_pendientes': citas.filter(estado=ESTADO_PENDIENTE).count(),
        'citas_canceladas': citas.filter(estado=ESTADO_CANCELADA).count(),
    }

    return render(request, 'sitio/mis_citas.html', context)


def cancelar_cita(request, id_cita):
    """Cancela una cita. El cliente solo las suyas; el administrador, cualquiera."""
    usuario = _usuario_en_sesion(request)

    if usuario is None:
        return redirect(f"{reverse('login')}?next={reverse('mis_citas')}")

    administrador = _es_administrador(usuario)
    destino = 'citas' if administrador else 'mis_citas'
    cita = Cita.objects.filter(pk=id_cita).first()

    if cita is None:
        messages.error(request, 'La cita que quieres cancelar ya no existe.')
        return redirect(destino)

    if not administrador and cita.id_usuario_id != usuario.id_usuario:
        messages.error(request, 'Solo puedes cancelar las citas que agendaste tú.')
        return redirect('mis_citas')

    if request.method != 'POST':
        messages.error(request, 'Usa el botón de cancelar de la lista para anular una cita.')
        return redirect(destino)

    if _cita_cancelada(cita):
        messages.info(request, 'Esa cita ya estaba cancelada.')
        return redirect(destino)

    cita.estado = ESTADO_CANCELADA
    cita.save(update_fields=['estado'])

    fecha_texto = f'{cita.fecha:%d/%m/%Y}' if cita.fecha else 'la fecha registrada'
    messages.success(
        request,
        f'La cita del {fecha_texto} quedó cancelada y su horario vuelve a estar disponible.'
    )

    return redirect(destino)


def eliminar_cita(request, id_cita):
    """Borra del registro una cita cancelada. Cliente: las suyas; admin: cualquiera."""
    usuario = _usuario_en_sesion(request)

    if usuario is None:
        return redirect(f"{reverse('login')}?next={reverse('mis_citas')}")

    administrador = _es_administrador(usuario)
    destino = 'citas' if administrador else 'mis_citas'
    cita = Cita.objects.filter(pk=id_cita).first()

    if cita is None:
        messages.error(request, 'La cita que quieres borrar ya no existe.')
        return redirect(destino)

    if not administrador and cita.id_usuario_id != usuario.id_usuario:
        messages.error(request, 'Solo puedes borrar las citas que agendaste tú.')
        return redirect('mis_citas')

    if request.method != 'POST':
        messages.error(request, 'Usa el botón de borrar de la lista para eliminar una cita.')
        return redirect(destino)

    if not _cita_cancelada(cita):
        messages.error(
            request,
            'Solo se pueden borrar las citas canceladas. Cancela la cita antes de eliminarla.'
        )
        return redirect(destino)

    fecha_texto = f'{cita.fecha:%d/%m/%Y}' if cita.fecha else 'la fecha registrada'
    cita.delete()
    messages.success(request, f'La cita cancelada del {fecha_texto} se borró del registro.')

    return redirect(destino)


def eliminar_citas_canceladas(request):
    """Borra todas las citas canceladas visibles para el usuario en sesión."""
    usuario = _usuario_en_sesion(request)

    if usuario is None:
        return redirect(f"{reverse('login')}?next={reverse('mis_citas')}")

    administrador = _es_administrador(usuario)
    destino = 'citas' if administrador else 'mis_citas'

    if request.method != 'POST':
        messages.error(request, 'Usa el botón de la lista para borrar las citas canceladas.')
        return redirect(destino)

    canceladas = Cita.objects.filter(estado=ESTADO_CANCELADA)

    if not administrador:
        canceladas = canceladas.filter(id_usuario=usuario)

    total = canceladas.count()

    if not total:
        messages.info(request, 'No había citas canceladas por borrar.')
        return redirect(destino)

    canceladas.delete()
    messages.success(
        request,
        f'Se borraron {total} cita' + ('' if total == 1 else 's') + ' cancelada'
        + ('' if total == 1 else 's') + ' del registro.'
    )

    return redirect(destino)


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

            cierre = _hora_cierre(fecha_cita)

            if fin.date() != fecha_cita:
                fin = None
                errores.append(
                    'La cita terminaría después de la medianoche, elige una hora más temprana.'
                )
            elif cierre and fin + timedelta(minutes=MARGEN_CIERRE_MIN) > datetime.combine(fecha_cita, cierre):
                errores.append(
                    f'{servicio.nombre} dura {servicio.duracion_min or DURACION_POR_DEFECTO} minutos '
                    f'y el salón cierra a las {cierre:%H:%M}. La cita debe terminar al menos '
                    f'{MARGEN_CIERRE_MIN} minutos antes del cierre; elige una hora más temprana.'
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
