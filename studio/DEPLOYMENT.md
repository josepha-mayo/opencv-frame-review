# Reproduce the bounded AWS demonstration

**26 October:** the live ECS application performs preparation, OpenCV 5 analysis and approval-bound encoding on real lesson excerpts. Compare `/api/deployment` with the dated release receipts linked from the repository README. Earlier credential-refresh notes are historical; accepted deployment requests, native qualification and completed live checks are separate evidence.

The verified deployment uses ECS Express Mode, Fargate, ECR, a managed HTTPS endpoint and CloudWatch Logs in us-east-1. ECS runs the actual media worker. There is no application task role and no model API key. AWS charges apply while the service and load balancer run.

1. Use an existing authenticated AWS CLI v2 profile. Build the Dockerfile on Linux, run all 14 verification stages with `python studio/run.py --verify NEW_OUTPUT`, then push the unchanged image to a private ECR repository. Set immutable tags and scan-on-push. Record the returned image digest and use `repository@sha256:...` below; a mutable tag is insufficient.
2. Create a dedicated ECS execution role trusted by `ecs-tasks.amazonaws.com`, with `AmazonECSTaskExecutionRolePolicy`. Create a separate infrastructure role trusted by `ecs.amazonaws.com`, constrained by your account and ECS source ARN, with `AmazonECSInfrastructureRoleforExpressGatewayServices`. The included `cloud/infrastructure-supplement.json` documents the narrowly scoped supplement required by this deployment; substitute your account, region, service and dedicated role names. The managed policy alone lacked ECS UpdateService/DescribeServices and CloudWatch DescribeAlarms during this trial.
3. Create `/opencv-creator/lesson-rescue` in CloudWatch Logs and set seven-day retention. Copy the create template below to a local JSON file and replace every placeholder. Use one replica, CPU 1024 and memory 2048. The initial hostname is a deliberately invalid placeholder; after creation, read the generated endpoint and update `PUBLIC_HOSTS` to its exact hostname.
4. Run `aws ecs create-express-gateway-service --region us-east-1 --cli-input-json file://create.json`. If first-time service-linked-role propagation fails, inspect the role and actual failure before retrying. Do not treat an accepted create response as a working deployment.
5. Read `aws ecs describe-express-gateway-service --service-arn YOUR_SERVICE_ARN --region us-east-1`. Prepare an update JSON containing `serviceArn` and the entire `primaryContainer` below, with the real assigned hostname, and run `aws ecs update-express-gateway-service --region us-east-1 --cli-input-json file://update.json`. Preserve the other fields. Express canary rollout can temporarily run two tasks; wait for the new revision to become active.
6. Wait for the intended deployment to complete with one running task and the pinned image digest. Check HTTPS `/health` and `/api/deployment`; match the 119-file source manifest to `studio/BUILD_HASHES.json`. Follow the current README route using the real package-progress lesson: inspect both states and teaching areas, check a fresh plan, explicitly approve QA generation, inspect teaching PNGs and cut points, and save/extract the rescue pack. Verify every member hash and compare downloaded media to native qualification. Separately test timestamp setup, no-proposal/refused outcomes and the explicit four-second recovery route. A request without the owning cookie must get 404 for a known job. A 375px browser viewport is not a physical-phone test. An HTTP 200 or an ACTIVE service alone does not establish media qualification.

```json
{
  "serviceName": "lesson-rescue",
  "executionRoleArn": "<EXECUTION_ROLE_ARN>",
  "infrastructureRoleArn": "<INFRASTRUCTURE_ROLE_ARN>",
  "healthCheckPath": "/health",
  "primaryContainer": {
    "image": "<ECR_REPOSITORY>@sha256:<VERIFIED_IMAGE_DIGEST>",
    "containerPort": 8877,
    "command": ["python", "studio/cloud_server.py"],
    "environment": [{"name":"PUBLIC_HOSTS","value":"replace-after-creation.invalid"}],
    "awsLogsConfiguration": {"logGroup":"/opencv-creator/lesson-rescue","logStreamPrefix":"creator"}
  },
  "cpu": "1024",
  "memory": "2048",
  "scalingTarget": {"minTaskCount":1,"maxTaskCount":1}
}
```

Default-VPC managed networking was used in the recorded deployment. A different account without a suitable VPC needs explicit networking configuration. Keep exactly one task in steady state: job ownership/storage is process-local, and scaling across tasks is unsupported. There is one worker, eight job slots, disk/request caps and 24-hour inactive-job expiry. Deployments can clear jobs sooner. Download evidence before replacing tasks.

The public intake accepts bounded MP4/MOV, WebM and Ogg/Theora uploads through an isolated preparation subprocess. Keep the documented 64 MiB, codec/track, 8-bit SDR, resolution, excerpt, time, process and disk caps. The bundled examples remain hash-checked. The frozen runtime has known package-scan findings; mitigation is not a security certification. Run as UID 10001 without an application AWS API role. Preserve strict CSP, host/origin/request-token and cookie checks. Exact edit preservation compares with the prepared source; preparation itself changes picture/audio and the original upload stays separate.

The README links current source/image, native and browser receipts; older evidence stays in its dated folders. Current interface layers over a qualified image are not fresh cold dependency rebuilds. Windows source/DOM checks do not qualify Linux media processing. Human outcomes remain separate from software QA. No credentials, session cookies or private ECR pull credentials are distributed. To retire a separate reproduction, delete its Express service through ECS and remove its dedicated resources only after confirming no other workloads depend on them.
