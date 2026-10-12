PY=python3
PELICAN=pelican
PELICANOPTS=

BASEDIR=$(CURDIR)
INPUTDIR=$(BASEDIR)/content
OUTPUTDIR=$(BASEDIR)/output
CONFFILE=$(BASEDIR)/pelicanconf.py
PUBLISHCONF=$(BASEDIR)/publishconf.py

FTP_HOST=localhost
FTP_USER=anonymous
FTP_TARGET_DIR=/

SSH_HOST=centerforopenneuroscience.org
SSH_TARGET_DIR=/srv/centerforopenneuroscience.org/www

S3_BUCKET=my_s3_bucket

CLOUDFILES_USERNAME=my_rackspace_username
CLOUDFILES_API_KEY=my_rackspace_api_key
CLOUDFILES_CONTAINER=my_cloudfiles_container

DROPBOX_DIR=~/Dropbox/Public/

# --- projection (orinoco-lite): con-site-specific -> this repo ---------
# The record store is the source of truth; everything below is derived from
# it and must not be hand-edited.  Paths are kept RELATIVE because they are
# handed to `datalad run`, which records them verbatim into the commit --
# an absolute path there is not reproducible on another checkout.
STORE=sourcedata/con-site-specific
PROJECTION_INPUTS=-i $(STORE)/metadata/records -i $(STORE)/content \
                  -i content/section-intros.yaml
PROJECTION_OUTPUTS=-o content/pages/whoweare.html \
                   -o content/pages/projects.html -o theme/static/img
MSG?=project: re-render the pages from con-site-specific

DEBUG ?= 0
ifeq ($(DEBUG), 1)
	PELICANOPTS += -D
endif

help:
	@echo 'Makefile for a pelican Web site                                        '
	@echo '                                                                       '
	@echo 'Usage:                                                                 '
	@echo '   make project                     project con-site-specific -> pages '
	@echo '   make run-project                 the same, under datalad run         '
	@echo '   make html                        (re)generate the web site          '
	@echo '   make clean                       remove the generated files         '
	@echo '   make regenerate                  regenerate files upon modification '
	@echo '   make publish                     generate using production settings '
	@echo '   make serve [PORT=8000]           serve site at http://localhost:8000'
	@echo '   make devserver [PORT=8000]       start/restart develop_server.sh    '
	@echo '   make stopserver                  stop local server                  '
	@echo '   make ssh_upload                  upload the web site via SSH        '
	@echo '   make rsync_upload                upload the web site via rsync+ssh  '
	@echo '   make dropbox_upload              upload the web site via Dropbox    '
	@echo '   make ftp_upload                  upload the web site via FTP        '
	@echo '   make s3_upload                   upload the web site via S3         '
	@echo '   make cf_upload                   upload the web site via Cloud Files'
	@echo '   make github                      upload the web site via gh-pages   '
	@echo '                                                                       '
	@echo 'Set the DEBUG variable to 1 to enable debugging, e.g. make DEBUG=1 html'
	@echo '                                                                       '

# Every script that writes into this repo from the record store, in the
# order the result depends on: the assets have to be in the theme before a
# page can reference one.  Run this and `git diff` is the projection.
project:
	$(PY) scripts/sync_assets_to_theme.py --write
	$(PY) scripts/render_whoweare.py --out content/pages/whoweare.html
	$(PY) scripts/render_projects.py --out content/pages/projects.html

# The same, with provenance: one commit carrying the command, the store it
# read and the files it wrote, which `datalad rerun` can replay.
#
# --explicit because the working tree normally carries unrelated untracked
# files, and without it `datalad run` refuses to start.  It also means the
# declared inputs and outputs are the whole of what the command may touch,
# so a new generated path has to be added to PROJECTION_OUTPUTS above or it
# will not be saved.
#
# The recorded command is the literal string "make project", NOT $(MAKE):
# GNU make executes any recipe line containing $(MAKE) even under `-n`, so
# writing it that way made `make -n run-project` really run datalad --
# which fetched the inputs, updated the submodule from its remote and
# unlocked 56 annexed logos before the dry run was over.
#
# Note that `datalad run` GETS its inputs, and for a submodule input that
# means `datalad update`: it may fetch and merge the record store from its
# remote, and commit the new submodule pointer here.  That is provenance
# working as intended, but it does touch the network and the store's
# history, so run this when you mean to.
run-project:
	datalad run --explicit -m "$(MSG)" \
	  $(PROJECTION_INPUTS) $(PROJECTION_OUTPUTS) \
	  "make project"

html:
	umask 022; $(PELICAN) $(INPUTDIR) -o $(OUTPUTDIR) -s $(CONFFILE) $(PELICANOPTS)

clean:
	[ ! -d $(OUTPUTDIR) ] || rm -rf $(OUTPUTDIR)

regenerate:
	$(PELICAN) -r $(INPUTDIR) -o $(OUTPUTDIR) -s $(CONFFILE) $(PELICANOPTS)

serve:
ifdef PORT
	cd $(OUTPUTDIR) && $(PY) -m pelican.server $(PORT)
else
	cd $(OUTPUTDIR) && $(PY) -m pelican.server
endif

devserver:
ifdef PORT
	$(BASEDIR)/develop_server.sh restart $(PORT)
else
	$(BASEDIR)/develop_server.sh restart
endif

stopserver:
	kill -9 `cat pelican.pid`
	kill -9 `cat srv.pid`
	@echo 'Stopped Pelican and SimpleHTTPServer processes running in background.'

publish:
	$(PELICAN) $(INPUTDIR) -o $(OUTPUTDIR) -s $(PUBLISHCONF) $(PELICANOPTS)

ssh_upload: publish
	scp -r $(OUTPUTDIR)/* $(SSH_HOST):$(SSH_TARGET_DIR)

rsync_upload: publish
	rsync -rvz --delete --chmod=ugo=rwX $(OUTPUTDIR)/ $(SSH_HOST):$(SSH_TARGET_DIR)

dropbox_upload: publish
	cp -r $(OUTPUTDIR)/* $(DROPBOX_DIR)

ftp_upload: publish
	lftp ftp://$(FTP_USER)@$(FTP_HOST) -e "mirror -R $(OUTPUTDIR) $(FTP_TARGET_DIR) ; quit"

s3_upload: publish
	s3cmd sync $(OUTPUTDIR)/ s3://$(S3_BUCKET) --acl-public --delete-removed

cf_upload: publish
	cd $(OUTPUTDIR) && swift -v -A https://auth.api.rackspacecloud.com/v1.0 -U $(CLOUDFILES_USERNAME) -K $(CLOUDFILES_API_KEY) upload -c $(CLOUDFILES_CONTAINER) .

github: publish
ifeq ($(TRAVIS_PULL_REQUEST), false)
	ghp-import -n $(OUTPUTDIR)
	@git push -fq https://${GH_TOKEN}@github.com/$(TRAVIS_REPO_SLUG).git gh-pages > /dev/null
endif
.PHONY: project run-project html help clean regenerate serve devserver publish ssh_upload rsync_upload dropbox_upload ftp_upload s3_upload cf_upload github
