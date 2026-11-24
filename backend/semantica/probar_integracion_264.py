
"""Prueba manual de punta a punta: JWT -> FastAPI -> Fuseki.

No usa Swagger, no guarda ni imprime la contraseña ni el token.
Usar una cuenta académica/de prueba, no datos privados reales.
"""

import getpass
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = 'http://127.0.0.1:8000'


def pedir(ruta, metodo='GET', cuerpo=None, token=None, tipo='application/json'):
    if cuerpo is None:
        datos = None
    elif tipo == 'application/x-www-form-urlencoded':
        datos = urlencode(cuerpo).encode('utf-8')
    else:
        datos = json.dumps(cuerpo).encode('utf-8')
    headers = {'Content-Type': tipo, 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    peticion = Request(BASE + ruta, data=datos, method=metodo, headers=headers)
    try:
        with urlopen(peticion, timeout=30) as respuesta:
            return json.loads(respuesta.read().decode('utf-8'))
    except HTTPError as exc:
        raise RuntimeError(f'HTTP {exc.code}: {exc.read(600).decode("utf-8", errors="replace")}') from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f'No se pudo conectar: {exc}') from exc


def main():
    print('PRUEBA SEMANTICA 26.4: utiliza una cuenta de prueba.')
    correo = input('Correo de la cuenta de prueba: ').strip()
    clave = getpass.getpass('Contraseña (oculta): ')
    autenticacion = pedir(
        '/auth/login', 'POST',
        {'username': correo, 'password': clave},
        tipo='application/x-www-form-urlencoded',
    )
    token = autenticacion['access_token']
    resultado = pedir('/consultas/semantica/sincronizar', 'POST', token=token)
    consulta = pedir('/consultas/semantica/cuentas', token=token)
    print('Sincronizacion:', resultado['resultado'])
    print('Triples exportados:', resultado['triples'])
    print('Entidades:', resultado['entidades'])
    print('Cuentas leidas mediante SPARQL:')
    for cuenta in consulta['cuentas']:
        print(
            f"  {cuenta['nombre_cuenta']}: "
            f"real={cuenta['saldo_real']}; "
            f"reservado={cuenta['monto_reservado']}; "
            f"libre={cuenta['saldo_libre']}"
        )
    print('Fin. Recuerda que el RDF es una instantánea, no tiempo real.')


if __name__ == '__main__':
    main()
