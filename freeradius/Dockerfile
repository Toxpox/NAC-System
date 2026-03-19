FROM freeradius/freeradius-server:latest

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends freeradius-rest && \
    rm -rf /var/lib/apt/lists/*

COPY clients.conf /etc/freeradius/clients.conf
COPY mods-enabled/rest /etc/freeradius/mods-enabled/rest
COPY sites-available/default /etc/freeradius/sites-available/default
COPY sites-available/default /etc/freeradius/sites-enabled/default

RUN rm -f /etc/freeradius/sites-enabled/inner-tunnel \
    /etc/freeradius/mods-enabled/eap && \
    chmod 640 /etc/freeradius/clients.conf \
    /etc/freeradius/mods-enabled/rest \
    /etc/freeradius/sites-available/default \
    /etc/freeradius/sites-enabled/default && \
    chown freerad:freerad /etc/freeradius/clients.conf \
    /etc/freeradius/mods-enabled/rest \
    /etc/freeradius/sites-available/default \
    /etc/freeradius/sites-enabled/default
