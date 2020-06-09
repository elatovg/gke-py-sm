# gke-py-sm

Quick demo of using GCP Secret Manager on GKE with the python client libraries.

## Create Secret and a Service Account with Appropriate IAM Permissions
Let's [create a secret](https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets#secretmanager-create-secret-cli):

```bash
> gcloud secrets create my-secret --replication-policy automatic
```

Next let's create a *version* of a secret:

```bash
> echo -n "myCoolSecret" | gcloud secrets versions add my-secret --data-file -
Created version [1] of the secret [my-secret].
```

Confirm it's there:

```bash
> gcloud secrets versions access 1 --secret my-secret
myCoolSecret%
```

Now let's create a Google Service Account with the [permissions to read the secret](https://cloud.google.com/secret-manager/docs/managing-secrets#secretmanager-create-secret-cli):

```bash
> export PROJECT=$(gcloud config list --format 'value(core.project)')
> gcloud iam service-accounts create secret-reader
> gcloud secrets add-iam-policy-binding my-secret --member serviceAccount:secret-reader@$PROJECT.iam.gserviceaccount.com --role roles/secretmanager.secretAccessor
```

As a quick test we can also download the private key and try to read the as the *Google Service Account* (this is optional):

```bash
> gcloud iam service-accounts keys create $PROJECT-secret-read.json --iam-account secret-reader@$PROJECT.iam.gserviceaccount.com
> gcloud auth activate-service-account --key-file $PROJECT-secret-read.json
```

And for the confirmation:

```bash
> gcloud secrets versions access 1 --secret my-secret
myCoolSecret%
```

Cool, the *Google Service Account* and permissions are all set. You can delete the key for security purposes:

```bash
> gcloud auth revoke secret-reader@$PROJECT.iam.gserviceaccount.com
> gcloud iam service-accounts keys list --iam-account secret-reader@$PROJECT.iam.gserviceaccount.com
> gcloud iam service-accounts keys delete cee9f3479c82815af573eb26b26fc2aaad508369 --iam-account secret-reader@$PROJECT.iam.gserviceaccount.com -q
```

## Create GKE cluster with Workload Identity

Next let's create a GKE cluster with [workload identity enabled](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#enable_on_new_cluster):

```bash
> gcloud beta container clusters create secret-demo --workload-pool=$PROJECT.svc.id.goog --zone us-east4-c
```

Now let's allow the **default** *Kubernetes Service Account* in the **default** namespace to run as the *Google Service Account* that we created ([Creating a relationship between KSAs and GSAs](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#creating_a_relationship_between_ksas_and_gsas)). This is done with two steps, first give the *Kubernetes Service Account* the **workloadIdentityUser** Role

```bash
> gcloud iam service-accounts add-iam-policy-binding --role roles/iam.workloadIdentityUser --member "serviceAccount:$PROJECT.svc.id.goog[default/default]" secret-reader@$PROJECT.iam.gserviceaccount.com
```

And second let's annotate the *Kubernetes Service Account* with the *Google Service Account*:

```bash
> kubectl annotate serviceaccount --namespace default default iam.gke.io/gcp-service-account=secret-reader@$PROJECT.iam.gserviceaccount.com
```

As a last test we can quickly deploy a pod with gcloud sdk installed and make sure we can get the secret:

```bash
> kubectl run -it --rm test --image google/cloud-sdk:slim --restart Never --command -- /bin/bash
If you don't see a command prompt, try pressing enter.
root@test:/# gcloud auth list
                  Credentialed Accounts
ACTIVE  ACCOUNT
*       secret-reader@demo.iam.gserviceaccount.com

To set the active account, run:
    $ gcloud config set account `ACCOUNT`

root@test:/# gcloud secrets versions access 1 --secret my-secret
myCoolSecret
root@test:/#
```

## Create a Container Image with Client Libraries

I ended up creating github repo for the demo taking the sample from [python client libraries](https://cloud.google.com/secret-manager/docs/reference/libraries#client-libraries-usage-python). So let's check that out and first build the docker image which has a python app that just prints out the secret value:

```bash
> git clone https://github.com/elatovg/gke-py-sm.git
> cd gke-py-sm/src
> docker build -t gcr.io/$PROJECT/py-sec-mngr:0.0.1 .
Sending build context to Docker daemon   5.12kB
Step 1/6 : FROM python:3.7-slim
...
 ---> 0d959b88d870
Successfully built 0d959b88d870
Successfully tagged gcr.io/demo/py-sec-mngr:0.0.1
> docker push gcr.io/$PROJECT/py-sec-mngr:0.0.1
```

Confirm the image is available in GCR:

```bash
> gcloud container images list --filter py-sec-mngr
NAME
gcr.io/demo/py-sec-mngr
```

## Start Pod with Workload Identity
Now that we have the image in GCR, let's deploy our pod with a deployment. First let's update the configs:

```bash
> cd ../k8s/
> gsed -i "s^image: py-sec-mngr^image: gcr.io/$PROJECT_ID/py-sec-mngr:0.0.1^g" deploy.yaml
> gsed -i "s^PROJECT_ID^$PROJECT_ID^g" cm.yaml
> gsed -i "s^SECRET_NAME^my-secret^g" cm.yaml
```

Now let's start the pod:

```bash
> k apply -f .
configmap/env-config created
deployment.apps/py-sec-mngr created
```

Now let's configure a port-forward to the pod:

```bash
> k port-forward $(kubectl get pod -l app=py-sec-mngr -o jsonpath='{.items[].metadata.name}') 8000:8000
```

And then from another shell `curl` the pod:

```bash
> curl localhost:8000
the secret is myCoolSecret
```

Yay that worked out :)