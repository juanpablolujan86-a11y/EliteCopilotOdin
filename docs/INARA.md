# Integración de ODIN con Inara

Inara requiere que el nombre de cada aplicación sea autorizado antes de usar la
API. Cada comandante aporta su propia clave desde Configuración y ODIN la guarda
mediante el almacén seguro del sistema operativo.

## Texto sugerido para enviar a Inara

Application name: `ODIN`

General purpose:

> ODIN is a local, modular co-pilot for Elite Dangerous. It reads the player's
> local Journal and provides exploration, exobiology, route planning and trade
> assistance. Its optional Inara integration synchronizes only the commander's
> own account data using that commander's personal API key. Network integrations
> are opt-in and all in-game actions remain under player control.

Short application description:

> Local Elite Dangerous co-pilot with optional commander profile, travel, ship,
> inventory, Powerplay and mission synchronization.

API endpoint and application identifier:

- Endpoint: `https://inara.cz/inapi/v1/`
- `appName`: `ODIN`
- Development requests set `isBeingDeveloped: true`.
- Requests are batched and normally sent no more frequently than once per minute.

Events currently implemented:

- `setCommanderCredits`
- `setCommanderGameStatistics`
- `setCommanderRankPilot`
- `setCommanderRankPower`
- `setCommanderReputationMajorFaction`
- `setCommanderReputationMinorFaction`
- `setCommanderInventoryCargo`
- `setCommanderInventoryMaterials`
- `setCommanderStorageModules`
- `setCommanderShip`
- `setCommanderShipLoadout`
- `setCommanderShipTransfer`
- `addCommanderTravelCarrierJump`
- `addCommanderTravelDock`
- `addCommanderTravelFSDJump`
- `addCommanderTravelLand`
- `setCommanderTravelLocation`
- `addCommanderMission`
- `setCommanderMissionAbandoned`
- `setCommanderMissionCompleted`
- `setCommanderMissionFailed`

## Estado de activación

El nombre de aplicación `ODIN` está autorizado por Inara. Captura y envío siguen
siendo voluntarios y se habilitan por separado en Configuración. Los fallos de
red quedan en la cola local y nunca deben bloquear el Journal.

No use credenciales reales en fixtures, commits, informes o capturas. Consulte
`SECURITY.md` y las pruebas `tests/test_inara_*.py`.
