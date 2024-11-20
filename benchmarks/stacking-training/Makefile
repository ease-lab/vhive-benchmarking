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
HERE = ./benchmarks/stacking-training

PLATFORM = --platform linux/amd64
MODE = --load

# For debugging on Apple M1 below
#PLATFORM = --platform linux/arm64
#MODE = --push

.PHONY: proto

all: all-image all-image-lambda

all-image: driver-image trainer-image reducer-image metatrainer-image

all-image-lambda: driver-image-lambda trainer-image-lambda reducer-image-lambda metatrainer-image-lambda

all-push: all-image-push all-image-lambda-push

all-image-push: driver-image-push trainer-image-push reducer-image-push metatrainer-image-push

all-image-lambda-push: driver-image-lambda-push trainer-image-lambda-push reducer-image-lambda-push metatrainer-image-lambda-push

driver-image: docker/Dockerfile proto/stacking_pb2_grpc.py proto/stacking_pb2.py driver/main.py
	docker buildx build $(PLATFORM) \
	-t vhiveease/stacking-training-driver:latest \
	--build-arg target_arg=driver \
	--secret id=GOPRIVATE_KEY \
	-f docker/Dockerfile \
	$(ROOT) $(MODE)

trainer-image: docker/Dockerfile proto/stacking_pb2_grpc.py proto/stacking_pb2.py trainer/main.py
	docker buildx build $(PLATFORM) \
	-t vhiveease/stacking-training-trainer:latest \
	--build-arg target_arg=trainer \
	--secret id=GOPRIVATE_KEY \
	-f docker/Dockerfile \
	$(ROOT) $(MODE)

reducer-image: docker/Dockerfile proto/stacking_pb2_grpc.py proto/stacking_pb2.py reducer/main.py
	docker buildx build $(PLATFORM) \
	-t vhiveease/stacking-training-reducer:latest \
	--build-arg target_arg=reducer \
	--secret id=GOPRIVATE_KEY \
	-f docker/Dockerfile \
	$(ROOT) $(MODE)

metatrainer-image: docker/Dockerfile proto/stacking_pb2_grpc.py proto/stacking_pb2.py metatrainer/main.py
	docker buildx build $(PLATFORM) \
	-t vhiveease/stacking-training-metatrainer:latest \
	--build-arg target_arg=metatrainer \
	--secret id=GOPRIVATE_KEY \
	-f docker/Dockerfile \
	$(ROOT) $(MODE)

driver-image-lambda: docker/Dockerfile.Lambda driver/main.py
	docker buildx build $(PLATFORM) \
	-t $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/stacking-training-driver:latest \
	--build-arg target_arg=driver \
	-f docker/Dockerfile.Lambda \
	$(ROOT) $(MODE)

trainer-image-lambda: docker/Dockerfile.Lambda trainer/main.py
	docker buildx build $(PLATFORM) \
	-t $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/stacking-training-trainer:latest \
	--build-arg target_arg=trainer \
	-f docker/Dockerfile.Lambda \
	$(ROOT) $(MODE)

reducer-image-lambda: docker/Dockerfile.Lambda reducer/main.py
	docker buildx build $(PLATFORM) \
	-t $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/stacking-training-reducer:latest \
	--build-arg target_arg=reducer \
	-f docker/Dockerfile.Lambda \
	$(ROOT) $(MODE)

metatrainer-image-lambda: docker/Dockerfile.Lambda metatrainer/main.py
	docker buildx build $(PLATFORM) \
	-t $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/stacking-training-metatrainer:latest \
	--build-arg target_arg=metatrainer \
	-f docker/Dockerfile.Lambda \
	$(ROOT) $(MODE)

driver-image-push: driver-image
	docker push vhiveease/stacking-training-driver:latest

trainer-image-push: trainer-image
	docker push vhiveease/stacking-training-trainer:latest

reducer-image-push: reducer-image
	docker push vhiveease/stacking-training-reducer:latest

metatrainer-image-push: metatrainer-image
	docker push vhiveease/stacking-training-metatrainer:latest

driver-image-lambda-push: driver-image-lambda
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin \
		$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	python $(ROOT)/runner/aws_lambda_scripts/aws_actions.py create_ecr_repo -n stacking-training-driver
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/stacking-training-driver:latest

trainer-image-lambda-push: trainer-image-lambda
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin \
		$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	python $(ROOT)/runner/aws_lambda_scripts/aws_actions.py create_ecr_repo -n stacking-training-trainer
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/stacking-training-trainer:latest

reducer-image-lambda-push: reducer-image-lambda
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin \
		$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	python $(ROOT)/runner/aws_lambda_scripts/aws_actions.py create_ecr_repo -n stacking-training-reducer
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/stacking-training-reducer:latest

metatrainer-image-lambda-push: metatrainer-image-lambda
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin \
		$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	python $(ROOT)/runner/aws_lambda_scripts/aws_actions.py create_ecr_repo -n stacking-training-metatrainer
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/stacking-training-metatrainer:latest

proto: proto/stacking.proto proto/helloworld.proto
	python -m grpc_tools.protoc -I./proto --python_out=./proto --grpc_python_out=./proto ./proto/stacking.proto
	python -m grpc_tools.protoc -I./proto --python_out=./proto --grpc_python_out=./proto ./proto/helloworld.proto
