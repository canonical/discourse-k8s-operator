# How to access the Rails console

Ideally, the discourse charm should be handled by interacting with Juju, and everything that can be done with the console should
be doable with juju actions. In case there is something that needs to be done with the console anyway, the console can be accessed.

### Prerequisites

Have a Discourse deployment active.

### Access the console

First of all, switch into the juju Discourse model if necessary:
```
juju switch discourse-model
```
Then ssh into the Discourse unit:
```
juju ssh --container discourse discourse-k8s/leader bash   
```
Now populate the required environment variables:
```
xargs -0 -L1 -a "/proc/$(ps aux | awk '/[a]pp_launch/ {print $2;exit}')/environ" | awk '{FS="=";print "export " $1 "=\"" $2 "\""}' > /root/envi && . /root/envi && rm /root/envi
```
In newer versions of the charm (revision 70+), the command to execute is the following:
```
sudo -u _daemon_ xargs -0 -L1 -a "/proc/$(ps aux | awk '/[u]nicorn master/ {print $2;exit}')/environ" | awk '{FS="=";print "export " $1 "=\"" $2 "\""}' > /root/envi && . /root/envi && rm /root/envi
```
Now change to the appropiate directory and execute the command to access the console:
```
cd /srv/discourse/app
RAILS_ENV=production bin/bundle exec rails console
```
If the output of the last command contains something similar to this:
```
Loading production environment (Rails 7.0.5.1)
irb(main):001:0>
```
Congratulations, you have accessed the rails console.