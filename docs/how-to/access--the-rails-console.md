# How to access the Rails console

Ideally, the Discourse charm should be handled by interacting with Juju, and everything that can be done with the console should
be doable with Juju actions. In case there is something that needs to be done with the console anyway, the console can be accessed.

### Prerequisites

Have a Discourse deployment active.

### Access the console

First of all, switch into the Juju Discourse model if necessary:
```
juju switch discourse-model
```
Then ssh into the Discourse unit:
```
juju ssh --container discourse discourse-k8s/leader bash   
```
Now access the console using Pebble:
```
pebble exec --user=_daemon_ --context=discourse -w=/srv/discourse/app -ti -- /srv/discourse/app/bin/bundle exec rails console
```
If the output of the last command contains something similar to this:
```
Loading production environment (Rails 7.0.5.1)
irb(main):001:0>
```
Congratulations, you have accessed the rails console.