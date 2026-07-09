# Resumen técnico – monitor híbrido G90

## Estado del trabajo

Se ha consolidado una estrategia de captura de eventos basada principalmente en la **detección raw de tramas** recibidas por la nube simulada, usando como base el monitor híbrido original.

La parte de callbacks de `pyg90alarm` para armado/desarmado no ha quedado como vía principal en esta fase, porque en esta alarma concreta las operaciones activas sobre flags y algunas lecturas iniciales (`set_flag`, `get_host_info`, `get_host_status`) tienden a bloquearse o a agotar tiempo de espera. En cambio, la **recepción cloud + decodificación raw** sí ha quedado validada en pruebas reales.

## Conclusiones ya validadas

1. La recepción por `use_cloud_notifications()` + `listen_notifications()` funciona.
2. La captura raw es fiable para eventos de botones del panel y del mando.
3. El arranque del monitor debe ser rápido: no conviene bloquear el camino crítico con lecturas iniciales del panel.
4. La activación programática de `ARM_DISARM` puede quedarse colgada en esta alarma; se deja como intento con timeout, pero no como requisito para escuchar eventos.
5. El bloque de **eventos de botones** ya se considera cerrado y validado.

## Mapa de códigos validado

### Cambios de estado generales
- `04000001` -> ARMADO TOTAL
- `03000003` -> DESARMADO
- `09000002` -> ARMADO PARCIAL

### Eventos desde mando a distancia
- `66000a06` -> ARMADO TOTAL DESDE MANDO
- `66000a07` -> ARMADO PARCIAL DESDE MANDO
- `66000a08` -> DESARMADO DESDE MANDO
- `66000a09` -> SOS

### Detalle de origen para SOS
- `63000001` -> SOS DESDE MANDO - DETALLE ORIGEN
- `63000002` -> SOS DESDE PANEL - DETALLE ORIGEN

### Zonas cableadas
- `c4000201` -> ZONA CABLEADA 1 - ACTIVADA
- `c5000801` -> ZONA CABLEADA 2 - ACTIVADA
- `c6000301` -> ZONA CABLEADA 3 - ACTIVADA
- `c7000301` -> ZONA CABLEADA 4 - ACTIVADA

## Interpretación actual del protocolo

Con lo observado hasta ahora, la estructura práctica parece ser:

- Familia `04 / 03 / 09 ...`:
  cambios de estado generales del sistema.

- Familia `66 00 0A xx`:
  acciones de botones, especialmente del mando y eventos equivalentes.

- Familia `63 00 00 xx`:
  detalle adicional del origen del evento SOS.

## Comportamiento observado de la alarma

### Lo que funciona bien
- Configuración del cloud server de la alarma.
- Recepción de tráfico en la nube simulada.
- Detección de heartbeats.
- Detección de eventos raw con timestamp y código.
- Actualización de `last_device_packet_time`.

### Lo que da problemas o no conviene usar como base principal
- `alert_config.set_flag(...)` puede quedarse bloqueado.
- `get_host_info()` y `get_host_status()` pueden tardar mucho o devolver timeout/vacío.
- La ruta de callback oficial de armado/desarmado no ha quedado validada como vía principal en esta fase.

## Decisiones de diseño adoptadas

1. **Vía principal del monitor**: raw decoding.
2. **Callbacks oficiales**: se pueden conservar como apoyo, pero no son el núcleo.
3. **Arranque rápido**: primero escuchar; cualquier sondeo al panel va fuera del camino crítico.
4. **Códigos desconocidos**: nunca se descartan; se registran y luego se clasifican mediante pruebas reales.
5. **Base estable**: se deja una versión del monitor centrada en los eventos ya validados.

## Versión base dejada

Se deja como base de trabajo una versión consolidada del monitor:

- `g90_monitor_hibrido_base.py`

Características:
- arranque rápido;
- intento no bloqueante de activar `ARM_DISARM`;
- listener cloud operativo;
- watchdog;
- registro JSONL;
- mapa de códigos ya validado;
- estructura preparada para ampliar sensores y otros eventos.

## Próximo bloque de trabajo

El siguiente objetivo es capturar y clasificar los **eventos generados por sensores de la casa**.

Método recomendado:
1. provocar un evento real;
2. observar el `code_hex`;
3. anotar el significado validado;
4. incorporarlo al mapa base;
5. repetir.

## Notas operativas

- El fichero JSONL de eventos permite conservar trazas exactas de cada prueba.
- Conviene mantener los códigos raw aunque ya estén clasificados.
- El monitor debe seguir siendo tolerante a timeouts del panel.
- No conviene “adivinar” eventos: solo se consolidan cuando han sido provocados y observados.

## Estado final de esta fase

Fase cerrada: **eventos de botones del panel y del mando a distancia**.

Nueva fase en marcha: **eventos de sensores / zonas cableadas**.

Primer código de sensores validado de forma conservadora:
- `c4000201` -> **ZONA CABLEADA 1 - ACTIVADA**

Base ya lista para seguir ampliando con más sensores y zonas.

Observación adicional validada:
- `c7000301` se ha observado repetido y corresponde a **zona cableada 4 - activada**.


## Hallazgo clave sobre la nube simulada

### Mecanismo que realmente ha funcionado

Tras nuevas pruebas, queda validado que el mecanismo que ha permitido volver a recibir eventos en el PC no ha sido la reconfiguración lógica del panel mediante `set_cloud_server_address(...)`, sino la **redirección del tráfico cloud dentro de la propia alarma** usando `iptables` por telnet.

La regla que ha funcionado es:

```bash
iptables -t nat -A OUTPUT -p tcp -d 47.88.7.61 --dport 5678 -j DNAT --to-destination 192.168.11.142:5678
```

### Interpretación operativa

La arquitectura real queda así:

1. la alarma intenta conectar con su nube original (`47.88.7.61:5678`);
2. dentro de la propia alarma, `iptables` redirige ese tráfico a `192.168.11.142:5678`;
3. en el PC, el monitor híbrido escucha en `192.168.11.142:5678` y recibe los eventos.

### Evidencias observadas

Se ha verificado por telnet en la alarma:

- acceso correcto a shell BusyBox;
- inserción correcta de la regla NAT en la cadena `OUTPUT`;
- visualización correcta de la regla con `iptables -t nat -L OUTPUT -n -v --line-numbers`;
- recuperación de la recepción de eventos en el PC después de aplicar la regla.

### Conclusión técnica

El sistema queda validado así:

- **telnet a la alarma**: OK
- **inyección de regla DNAT en la alarma**: OK
- **recepción de eventos en el PC tras aplicar la regla**: OK

Por tanto, la recepción de eventos depende de que esa regla exista dentro de la alarma.

## Recuperación tras apagado o reinicio de la alarma

### Síntoma

Después de apagar o reiniciar la alarma, el monitor del PC puede quedar escuchando correctamente pero **sin recibir ningún evento**.

### Causa más probable

La regla `iptables` interna de la alarma no parece persistente, por lo que tras reinicio el tráfico vuelve a intentar salir hacia la nube original sin desviarse al PC.

### Procedimiento de recuperación validado

1. Entrar por telnet en la alarma.
2. Aplicar o reaplicar la regla:

```bash
iptables -t nat -C OUTPUT -p tcp -d 47.88.7.61 --dport 5678 -j DNAT --to-destination 192.168.11.142:5678 2>/dev/null || iptables -t nat -A OUTPUT -p tcp -d 47.88.7.61 --dport 5678 -j DNAT --to-destination 192.168.11.142:5678
```

3. Verificarla:

```bash
iptables -t nat -L OUTPUT -n -v --line-numbers
```

4. Arrancar en el PC el monitor:

```bash
source ~/g90env/bin/activate
python3 ~/alarma/g90_monitor_hibrido_base_v4.py
```

5. Probar un evento simple:
   - armado total
   - desarmado
   - botón del mando

### Resultado esperado

Si la regla ha quedado bien aplicada, el monitor del PC vuelve a recibir eventos.

## Script remoto validado para reaplicar la regla

Se ha preparado un script `expect` para automatizar desde el PC la inserción de la regla por telnet:

- `redirige_nube_alarma_v5.expect`

Ese script:
- entra por telnet en la alarma;
- comprueba acceso a shell;
- aplica la regla si no existe;
- muestra la tabla NAT `OUTPUT`;
- sale.

## Estado actualizado del proyecto

### Bloques validados

- captura de eventos de botones de panel y mando;
- captura de códigos raw;
- listener cloud en el PC;
- acceso telnet a la alarma;
- redirección efectiva del tráfico cloud mediante `iptables`;
- recuperación de la recepción tras reaplicar la regla.

### Bloques pendientes

- persistencia automática de la regla tras reinicio de la alarma;
- clasificación completa de sensores y zonas;
- canal de entrega a Android;
- estrategia permanente o periódica de aseguramiento de la nube simulada.

## Recomendación operativa actual

Mientras no se encuentre un mecanismo persistente dentro del sistema de la alarma, debe asumirse esta norma:

**si la alarma se apaga o reinicia, hay que volver a aplicar la regla DNAT antes de esperar eventos en el PC**.


Observación adicional validada:
- `c5000801` corresponde a **zona cableada 2 - activada**.

Observación adicional validada:
- `c6000301` corresponde a **zona cableada 3 - activada**.
