# MIT License
#
# Copyright (c) 2021 Dmitrii Ustiugov and EASE lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

ROOT = ../../
HERE = ./benchmarks/tuning-halving

PLATFORM = --platform linux/amd64
MODE = --load

# For debugging on Apple M1 below
#PLATFORM = --platform linux/arm64
#MODE = --push

.PHONY: proto

all: all-image all-image-lambda

all-image: driver-image trainer-image

all-image-lambda: driver-image-lambda trainer-image-lambda

all-push: all-image-push all-image-lambda-push

all-image-push: driver-image-push trainer-image-push

all-image-lambda-push: driver-image-lambda-push trainer-image-lambda-push

driver-image: docker/Dockerfile proto/tuning_pb2_grpc.py proto/tuning_pb2.py driver/main.py
	docker buildx build $(PLATFORM) \
	-t vhiveease/tuning-halving-driver:latest \
	--build-arg target_arg=driver \
	--secret id=GOPRIVATE_KEY \
	-f docker/Dockerfile \
	$(ROOT) $(MODE)

trainer-image: docker/Dockerfile proto/tuning_pb2_grpc.py proto/tuning_pb2.py trainer/main.py
	docker buildx build $(PLATFORM) \
	-t vhiveease/tuning-halving-trainer:latest \
	--build-arg target_arg=trainer \
	--secret id=GOPRIVATE_KEY \
	-f docker/Dockerfile \
	$(ROOT) $(MODE)

driver-image-lambda: docker/Dockerfile.Lambda driver/main.py
	docker buildx build $(PLATFORM) \
	-t $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/tuning-halving-driver:latest \
	--build-arg target_arg=driver \
	-f docker/Dockerfile.Lambda \
	$(ROOT) $(MODE)

trainer-image-lambda: docker/Dockerfile.Lambda trainer/main.py
	docker buildx build $(PLATFORM) \
	-t $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/tuning-halving-trainer:latest \
	--build-arg target_arg=trainer \
	-f docker/Dockerfile.Lambda \
	$(ROOT) $(MODE)

driver-image-push: driver-image
	docker push vhiveease/tuning-halving-driver:latest

trainer-image-push: trainer-image
	docker push vhiveease/tuning-halving-trainer:latest

driver-image-lambda-push: driver-image-lambda
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin \
		$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	python $(ROOT)/runner/aws_lambda_scripts/aws_actions.py create_ecr_repo -n tuning-halving-driver
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/tuning-halving-driver:latest

trainer-image-lambda-push: trainer-image-lambda
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin \
		$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	python $(ROOT)/runner/aws_lambda_scripts/aws_actions.py create_ecr_repo -n tuning-halving-trainer
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/tuning-halving-trainer:latest

proto: proto/tuning.proto proto/helloworld.proto
	python -m grpc_tools.protoc -I./proto --python_out=./proto --grpc_python_out=./proto ./proto/tuning.proto
	python -m grpc_tools.protoc -I./proto --python_out=./proto --grpc_python_out=./proto ./proto/helloworld.proto
