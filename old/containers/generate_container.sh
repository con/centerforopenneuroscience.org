#!/bin/bash

set -eu

generate() {
	# more details might come on https://github.com/ReproNim/neurodocker/issues/330
	[ "$1" == singularity ] && add_entry=' "$@"' || add_entry=''
	#neurodocker generate "$1" \
	ndversion=0.7.0
	#ndversion=master
	docker run --rm repronim/neurodocker:$ndversion generate "$1" \
		--base=neurodebian:jessie \
		--ndfreeze date=20200503 \
		--pkg-manager=apt \
		--install vim wget strace time ncdu gnupg curl procps pigz less tree \
				  python-pelican linkchecker git git-annex-standalone make
}

#generate docker > Dockerfile
generate singularity > Singularity

# fixup
sed -i -e '/su - root/d' Singularity
