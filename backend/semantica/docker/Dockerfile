
FROM eclipse-temurin:21-jre-jammy

ARG JENA_VERSION=6.3.0

ENV JAVA_TOOL_OPTIONS="-Xms128m -Xmx768m"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
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
        --gid fuseki \
        --create-home \
        --home-dir /home/fuseki \
        fuseki \
    && mkdir -p /datos/tdb2 \
    && chown -R fuseki:fuseki \
        /datos \
        /opt/fuseki

USER fuseki

WORKDIR /opt/fuseki

EXPOSE 3030

ENTRYPOINT ["java", "-cp", "/opt/fuseki/fuseki.jar", "org.apache.jena.fuseki.main.cmds.FusekiMainCmd"]
