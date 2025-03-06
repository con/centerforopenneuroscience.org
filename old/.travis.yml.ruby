language: ruby
rvm:
  - 1.9.3
branches:
  only:
  - master
before_install:
- sudo apt-get install python-pip
install:
- sudo pip install pelican==3.5.0 ghp-import markdown
- cd slate
- bundle install
script:
- cd ..
- make github
env:
  global:
    secure: AbFH4lZFUsoGe7OILV4jmEsKV93KeAfarKnvxGe56IDAKxIYPWtcIP9S3AAA5whdBQh3KR9+5XiBJ39fN6wZH2g14cbHQefM8GfH8OIB1DCe7nFQl6WxY+dhPR9TCKRg5QjMkPXTJo6PvASS6NcCumalIVFpJBE4lNyx6A0Ix2c=
