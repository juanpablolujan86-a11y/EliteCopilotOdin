from services.edsm_service import EDSMService

edsm = EDSMService()

system = edsm.get_system("Sol")

print(system)