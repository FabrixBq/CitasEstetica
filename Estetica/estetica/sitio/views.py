from django.shortcuts import render
from django.http import HttpResponse
from .models import Servicio, Cita, Horario, Usuario
# Create your views here.

def index(request):
    return render(request, 'sitio/index.html')

def servicios(request):
    listado_servicios = Servicio.objects.all()

    context = {
        'servicios': listado_servicios
    }

    return render(request, 'sitio/servicios.html', context)

def formulario(request):
    if request.method == 'POST':
        # Aquí puedes procesar los datos del formulario y guardarlos en la base de datos
        # Por ejemplo:
        nombre = request.POST.get('nombre')
        correo = request.POST.get('correo')
        psswd = request.POST.get('psswd')
        rol = request.POST.get('rol')

        # Crear un nuevo usuario
        nuevo_usuario = Usuario(nombre=nombre, correo=correo, psswd=psswd, rol=rol)
        nuevo_usuario.save()

        # Redirigir a una página de éxito o mostrar un mensaje
        return HttpResponse("Formulario enviado correctamente.")

    return render(request, 'sitio/formulario.html')