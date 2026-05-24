#!/bin/bash

set -x

echo "Updating the Kubernetes deployment..."

aws sts get-caller-identity
aws eks update-kubeconfig --region us-west-2 --name dev-cluster --kubeconfig ~/.kube/config
kubectl config use-context arn:aws:eks:us-west-2:142496269814:cluster/dev-cluster
kubectl config set-context --current --namespace=ons-climate-health

TOKEN=$(aws eks get-token --region us-west-2 --cluster-name dev-cluster --output json | jq -r '.status.token')
kubectl config set-credentials codepipeline --token="$TOKEN"
kubectl config set-context --current --user=codepipeline

echo "Checking kubectl version..."
kubectl version

PATCH_IMAGE_JSON=$(printf '[{"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "%s"}]' "142496269814.dkr.ecr.us-west-2.amazonaws.com/ons-climate-health/data-explorer:$VERSION")
kubectl patch deployment data-explorer -n ons-data-explorer --type='json' -p="$PATCH_IMAGE_JSON"

PATCH_ENV_JSON=$(printf '[{"op": "add", "path": "/spec/template/spec/containers/0/env/-", "value": {"name": "IMAGE_TAG_AND_BUILD_DATE", "value": "%s - %s"}}]' "$VERSION" "$(date)")
kubectl patch deployment data-explorer -n ons-data-explorer --type='json' -p="$PATCH_ENV_JSON"

echo "Kubernetes deployment updated"
