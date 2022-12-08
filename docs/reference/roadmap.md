Below is the roadmap for the Discourse K8s Operator.

## October 2022 to April 2023
* Transition to sidecar. The charm as currently published in the "stable" channel is using the older "pod-spec" approach to k8s charming. We plan to complete the conversion to the sidecar approach, adding liveness/readiness checks as appropriate.
* Update CI/CD. The IS DevOps team has some common workflows and we'll integrate with these to add linting, unit tests, static code analysis, integration tests and inclusive naming checks.
* Integration with [COS](https://charmhub.io/topics/canonical-observability-stack). 
* Documentation improvements - updating the home page, integrating the [Diataxis documentation framework](https://diataxis.fr/) and including project governance information.
* SAML integration test.
