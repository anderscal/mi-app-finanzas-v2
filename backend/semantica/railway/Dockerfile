FROM eclipse-temurin:21-jre-jammy

ARG JENA_VERSION=6.3.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gosu \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    mkdir -p /opt/fuseki; \
    URL="https://repo.maven.apache.org/maven2/org/apache/jena/jena-fuseki-server/${JENA_VERSION}/jena-fuseki-server-${JENA_VERSION}.jar"; \
    curl --fail --location --retry 3 \
        "$URL" \
        --output /opt/fuseki/fuseki.jar; \
    SHA1="$(curl --fail --silent --show-error --location --retry 3 "${URL}.sha1" | awk '{print $1}')"; \
    test -n "$SHA1"; \
    printf '%s  %s\n' "$SHA1" "/opt/fuseki/fuseki.jar" \
        | sha1sum --check -

RUN groupadd --system --gid 10001 fuseki \
    && useradd \
        --system \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        --home-dir /home/fuseki \
        fuseki \
    && mkdir -p \
        /datos/tdb2 \
        /opt/fuseki \
        /run/fuseki

COPY config.ttl /opt/fuseki/config.ttl

COPY log4j2.properties /opt/fuseki/log4j2.properties

COPY entrypoint.sh /opt/fuseki/entrypoint.sh

RUN sed -i 's/\r$//' /opt/fuseki/entrypoint.sh \
    && chmod 755 /opt/fuseki/entrypoint.sh

WORKDIR /opt/fuseki

EXPOSE 3030

ENTRYPOINT ["/opt/fuseki/entrypoint.sh"]