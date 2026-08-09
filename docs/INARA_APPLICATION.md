# Solicitud de autorización de ODIN para Inara

Inara requiere que el nombre de cada aplicación sea autorizado antes de usar la
API. La clave incluida en `INARA_API_KEY.txt` es la clave personal del comandante;
no reemplaza esta autorización de la aplicación.

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

Mantener `inara_capture_enabled` e `inara_upload_enabled` desactivados hasta que
Inara confirme que `ODIN` fue agregado a su lista autorizada. Después de la
confirmación se debe realizar primero una prueba controlada con una cuenta y
revisar las respuestas antes de habilitar la distribución general.
