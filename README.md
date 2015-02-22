# Scrappy DDNS
Scrappy DDNS is a Dynamic DNS-like service that sends push notifications to your mobile devices whenever your public IP address changes. It works in conjunction with DDNS clients built into many routers/firewalls such as [DD-WRT](http://www.dd-wrt.com/site/index) and [pfSense](https://www.pfsense.org/). But really, any client capable of making an HTTP request can work -- even a cron job that calls `curl` periodically will do in a pinch. Push notifications are sent via the awesome [Pushover](https://pushover.net/) service, which supports Android, iOS, and desktop systems.

# Why Scrappy?
So what good is a DDNS service that doesn't actually update DNS records? Scrappy might be right for you if:

* Your DNS hosting service doesn't support true Dynamic DNS and your IP address rarely changes.
* You prefer to manage DNS records manually.
* You just want to know whenever your IP address changes.

Scrappy is free software that you can install behind your firewall or on a hosted web server or VPS. The latter option is particularly useful when you want to monitor multiple networks or servers at the same time. You can assign friendly names to each one that will show up in the alerts.

# How it works
Scrappy DDNS is a simple Python web service. It listens for HTTP GET requests with a special token in the URL path that matches a network or server that it knows about. For example:
```
https://scrappy.example.com/NRmP324IsdSo2xidk69imtR2
```
When the service gets a request with a valid token, it compares the source IP address to the last known address for the same token. If there is a change, it sends an alert.

Alternatively, the public IP address can be given as a URL parameter:
```
https://scrappy.example.com/NRmP324IsdSo2xidk69imtR2?ip_address=1.2.3.4
```
This is necessary if the source IP address of the HTTP request is not the same as the public IP such as when Scrappy is installed behind the firewall. Naturally, this requires the client to [know](http://tecadmin.net/5-commands-to-get-public-ip-using-linux-terminal/) its public IP address. :-)

# Getting started
Before you begin, download the [Pushover](https://pushover.net) app and register on their web site to obtain a user key and an [application key](https://pushover.net/apps/clone/Scrappy_DDNS) for your copy of Scrappy DDNS. The service has a free trial period and no recurring fees after purchase of an app license.

> [Click here](https://pushover.net/apps/clone/Scrappy_DDNS) to create an application key using the Scrappy DDNS template. Ths saves some typing. You must be logged into the Pushover web site first.

Next, you need to create a token file called `token.list`. This is a text file that contains one line for each network or server you want to monitor. Each line must be of the form:
```
<token>:<name>
```
where `<token>` is an alphanumeric string that you assign to one server/network and `<name>` is a friendly name to appear in alerts. Tokens are like passwords. You can make them whatever you want, but they should be hard to guess because anyone who has them will be able to advertise a new IP address. GRC's [Perfect Passwords](https://www.grc.com/passwords.htm) page generates nice long random alphanumeric strings that are perfect as tokens. Here is an example token file:
```
# My home network
NRmP324IsdSo2xidk69imtR2:Home network
# Branch office (VPN)
VVko3dcRTdLbNFvvi35J3PqB:Main Street office
```
The Git repo has a sample `token.list` file that you can use as a template.

# Deployment
There are several ways to get the Scrappy DDNS up and running. From simple to complex, you can:

1. Run the Python script directly.
2. Run it inside a [Docker container](https://github.com/rhasselbaum/docker-scrappy-ddns).
3. Deploy it to an existing web server.

We'll cover each option below.

## Option 1: Run as a Python script

The simplest option is to run the Scrappy DDNS script (`scrappyddns.py`) from the command line. This is the least secure option and should be chosen only if you will run the service behind your firewall and you trust the people on your local network. SSL/TLS is not supported in this configuration so tokens will be sent unencrypted over the network.

> Do NOT choose this option if the service will be exposed on the Internet!

Scary disclaimers aside, this may be a good choice for home networks.

The script depends on **Python 3.4 or higher** and the **Flask** web microframework, so make sure those are installed. Next, clone the Git repo or download and extract the ZIP to a suitable directory that also contains your `token.list` file.

Modify the `scrappyddns.conf` file to include your user and application keys for Pushover notifications. Change other settings there as you wish. Note that the script needs read/write access to a directory that it can use to store the most recent IP addresses it has learned for each token. By default, the current directory will be used for this, but you can specify a different one in the `scrappyddns.conf` file.

Finally, change directory to the location of the `scrappyddns.conf` and `token.list` files and start the service with a command like:
```
python3 scrappyddns.py
```
This starts the service listening on port 5000. By default, the service accepts traffic on all network interfaces (bind address `0.0.0.0`). To bind to a particular interface and port instead, pass them as arguments:
```
python3 scrappyddns.py [<bind_address>] [<port>]
```
For example, to listen only for local connections on port 6000, you'd use:
```
python3 scrappyddns.py localhost 6000
```
The script can be started from an init system such as systemd to run as a persistent service. And the locations of log files, the IP address cache, and the `scrappyddns.conf` file can be configured to make Scrappy fit well within a standard Linux file system hierarchy. However, if you are serious about running the service in a robust and secure way, I strongly encourage you to choose one of the other deployment options instead. That brings us to...

## Option 2: Run inside a Docker container

The recommended way to run a standalone instance of Scrappy is as a [Docker](https://www.docker.com) container. The [rhasselbaum/scrappy-ddns](https://registry.hub.docker.com/u/rhasselbaum/scrappy-ddns) images on the Docker Hub run Scrappy DDNS under the Gunicorn container with SSL/TLS support for encrypted connections. For more information, visit my [repository](https://registry.hub.docker.com/u/rhasselbaum/scrappy-ddns) or the related [GitHub project](https://github.com/rhasselbaum/docker-scrappy-ddns) that contains the automated build files and instructions.

## Option 3: Deploy to an existing web server

Scrappy DDNS is a Flask web application that can be deployed to any WSGI-compliant container with Python 3 support including Apache (mod_wsgi), nginx (uWSGI), Waitress, Gunicorn, and others. You must have the **Flask** library installed and **Python 3.4 or higher** to run it. The Flask project's [deployment documentation](http://flask.pocoo.org/docs/0.10/deploying/) explains how to deploy to a number of these servers. If you have an existing web server and you're the DIY type, this might be a good option for you. Just make sure your server supports SSL/TLS to protect tokens in transit if it is exposed on the Internet.

By setting the environment variable `SCRAPPYDDNS_CONF`, you can specify the path and filename of the `scrappyddns.conf` file that holds all of the Scrappy DDNS configuration including the locations of the token list, logs, and cache directory.

# Client configuration

Coming soon!
