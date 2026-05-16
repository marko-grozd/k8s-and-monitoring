# k8s-and-monitoring
simple app for testing kubernetes and helm

```
 _   _      _ _            _    ___       _ 
| | | | ___| | | ___      | |  / _ \  ___| |
| |_| |/ _ \ | |/ _ \_____| | | (_) |/ __| |
|  _  |  __/ | | (_) |____| |  \__, / (__| |
|_| |_|\___|_|_|\___/      |_|    /_/ \___|_|
```

```
 ██╗  ██╗ █████╗ ███████╗
 ██║ ██╔╝██╔══██╗██╔════╝
 █████╔╝ ╚█████╔╝███████╗
 ██╔═██╗ ██╔══██╗╚════██║
 ██║  ██╗╚█████╔╝███████║
 ╚═╝  ╚═╝ ╚════╝ ╚══════╝
```
#how to start with makefile

make k8s-up           # Deploy aplikacije
make k8s-down         # Obrisi aplikaciju
make k8s-status       # Status svih resursa
make monitoring-up    # Deploy monitoring stacka
make monitoring-down  # Obrisi monitoring
make monitoring-status # Status monitoringa
make logs-backend     # Logovi backenda
make pf-grafana       # Port-forward Grafana
make pf-backend       # Port-forward backend