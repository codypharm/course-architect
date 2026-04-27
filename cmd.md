# API
aws logs tail /ecs/ai-course-architect-staging/api --since 10m --region eu-north-1

# Worker
aws logs tail /ecs/ai-course-architect-staging/worker --since 10m --region eu-north-1

# Beat
aws logs tail /ecs/ai-course-architect-staging/beat --since 10m --region eu-north-1

# Flower
aws logs tail /ecs/ai-course-architect-staging/flower --since 10m --region eu-north-1



aws logs tail /ecs/ai-course-architect-staging/api \
  --follow \
  --region eu-north-1


aws logs tail /ecs/ai-course-architect-staging/worker \
  --follow \
  --region eu-north-1

aws logs tail /ecs/ai-course-architect-staging/worker \
  --follow \
  --region eu-north-1 \
  --filter-pattern "<thread_id>"







cd infra/terraform/envs/staging
terraform destroy -auto-approve
The S3 Vectors vector bucket sits outside Terraform so it won't be touched. When you're ready to bring everything back up:


terraform apply -auto-approve
Then just recreate the index (bucket already exists, only the index needs recreating):


Force a new ECS deployment after filling secrets so the containers pick them up:
aws ecs update-service --cluster ai-course-architect-staging \
  --service api --force-new-deployment
aws ecs update-service --cluster ai-course-architect-staging \
  --service worker --force-new-deployment


To destroy staging manually:


cd infra/terraform/envs/staging
terraform init
terraform destroy -auto-approve
If it fails on non-empty S3 buckets or ECR, empty them first:


# Empty S3 buckets
aws s3 rm s3://ai-course-architect-staging-uploads --recursive
aws s3 rm s3://ai-course-architect-staging-frontend --recursive

# Force-delete ECR repo
aws ecr delete-repository --repository-name ai-course-architect --force --region us-east-1

# Then re-run destroy
terraform destroy -auto-approve


aws ecs update-service --cluster ai-course-architect-staging \
  --service api --force-new-deployment
aws ecs update-service --cluster ai-course-architect-staging \
  --service worker --force-new-deployment

aws s3vectors create-index \
  --vector-bucket-name ai-course-architect-staging-vectors \
  --index-name course-chunks \
  --data-type float32 \
  --dimension 1536 \
  --distance-metric cosine \
  --region eu-north-1
i will need to recreate the index ?
Yes, because the index lives inside the vector bucket and was created manually. The bucket persists but you'll need to check if the index survived — it should since you're not deleting the bucket.

Verify after destroy:


aws s3vectors list-indexes \
  --vector-bucket-name ai-course-architect-staging-vectors \
  --region eu-north-1
If course-chunks shows up, you don't need to recreate it. If it's empty, run the create-index command.