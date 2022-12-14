In this tutorial, we'll walk you through the process of deploying the indico charm, relating it to the nginx-ingress-integrator charm, the postgresql-k8s charm and the redis-k8s charm, and inspecting kubernetes resources it creates. We'll then also look at changing the charm configuration via a juju configuration update.

## Requirements

You will need:

* A laptop or desktop running Ubuntu (or you can use a VM).
* [Juju and Microk8s](https://juju.is/docs/olm/microk8s) installed. We’ll also want to make sure the ingress add-on is enabled, which we can do by running `microk8s enable ingress`.

## Deploy this charm

