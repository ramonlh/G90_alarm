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

Base ya lista para la siguiente fase: **eventos de sensores**.
