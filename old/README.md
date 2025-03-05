# Center for Open Neuroscience (CON)

This repository provides sources for the website at [http://centerforopenneuroscience.org](http://centerforopenneuroscience.org/)

## Website design

It is largely based on [buddycloud.com](http://buddycloud.com) design which was
released under Apache 2.0 license.  New content of the website is released
under CC BY 3.0 license.

## HOWTO

Install pelican (e.g. `pip install pelican`).
You might need to get files using `git-annex` so do `git annex get *`.
To start serving while developing

```shell
make devserver
```

and to stop later

```shell
make stopserver
```
