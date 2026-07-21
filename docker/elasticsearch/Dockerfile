FROM docker.elastic.co/elasticsearch/elasticsearch:8.17.0

ARG IK_VERSION=8.17.0

RUN bin/elasticsearch-plugin install --batch \
    "https://release.infinilabs.com/analysis-ik/stable/elasticsearch-analysis-ik-${IK_VERSION}.zip"
