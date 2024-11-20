# MIT License
#
# Copyright (c) 2021 EASE lab
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

import os
import sys

import tracing
from trainer import Trainer

import json
import logging as log
import pickle

LAMBDA = os.environ.get('IS_LAMBDA', 'no').lower() in ['true', 'yes', '1']

if not LAMBDA:
    import grpc
    import argparse
    import socket
    import stacking_pb2_grpc
    import stacking_pb2
    import destination as XDTdst
    import source as XDTsrc
    import utils as XDTutil

    from concurrent import futures

    parser = argparse.ArgumentParser()
    parser.add_argument("-dockerCompose", "--dockerCompose",
        dest="dockerCompose", default=False, help="Env docker compose")
    parser.add_argument("-sp", "--sp", dest="sp", default="80", help="serve port")
    parser.add_argument("-zipkin", "--zipkin", dest="zipkinURL",
        default="http://zipkin.istio-system.svc.cluster.local:9411/api/v2/spans",
        help="Zipkin endpoint url")

    args = parser.parse_args()

if tracing.IsTracingEnabled():
    tracing.initTracer("trainer", url=args.zipkinURL)
    tracing.grpcInstrumentClient()
    tracing.grpcInstrumentServer()

INLINE = "INLINE"
S3 = "S3"
XDT = "XDT"

if not LAMBDA:
    class TrainerServicer(stacking_pb2_grpc.TrainerServicer):
        def __init__(self, XDTconfig=None):
            self.trainer = Trainer(XDTconfig)

        def Train(self, request, context):
            trainingConfig = {
                'trainer_id': int(request.trainer_id),
                'dataset_key': request.dataset_key,
                'model_cfg': pickle.loads(request.model_config)
            }
            response = self.trainer.train(trainingConfig)

            return stacking_pb2.TrainReply(
                model=b'',
                model_key=response['model_key'],
                pred_key=response['pred_key']
            )

if LAMBDA:
    class AWSLambdaTrainer:
        def __init__(self):
            self.trainer = Trainer()

        def Train(self, event, context):
            trainingConfig = {
                'trainer_id': int(event['trainer_id']),
                'dataset_key': event['dataset_key'],
                'model_cfg': json.loads(event['model_cfg'])
            }
            response = self.trainer.train(trainingConfig)

            return {
                'model_key': response['model_key'],
                'pred_key': response['pred_key']
            }


def serve():
    transferType = os.getenv('TRANSFER_TYPE', S3)
    if transferType == S3:
        log.info("Using inline or s3 transfers")
        max_workers = int(os.getenv("MAX_SERVER_THREADS", 10))
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        stacking_pb2_grpc.add_TrainerServicer_to_server(
            TrainerServicer(), server)
        server.add_insecure_port('[::]:' + args.sp)
        server.start()
        server.wait_for_termination()
    elif transferType == XDT:
        log.fatal("XDT not yet supported")
    else:
        log.fatal("Invalid Transfer type")

def lambda_handler(event, context):
    log.basicConfig(level=log.INFO)
    trainerServicer = AWSLambdaTrainer()
    return trainerServicer.Train(event, context)

if not LAMBDA and __name__ == '__main__':
    log.basicConfig(level=log.INFO)
    serve()
