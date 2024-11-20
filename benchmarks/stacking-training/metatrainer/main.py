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

from metatrainer import Metatrainer
import tracing

import json
import logging as log
import pickle

LAMBDA = os.environ.get('IS_LAMBDA', 'no').lower() in ['true', 'yes', '1']

if not LAMBDA:
    import grpc
    import argparse
    import boto3
    import logging as log
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
    tracing.initTracer("metatrainer", url=args.zipkinURL)
    tracing.grpcInstrumentClient()
    tracing.grpcInstrumentServer()

INLINE = "INLINE"
S3 = "S3"
XDT = "XDT"

if not LAMBDA:
    class MetatrainerServicer(stacking_pb2_grpc.TrainerServicer):
        def __init__(self, XDTconfig=None):
            self.metatrainer = Metatrainer(XDTconfig)

        def Metatrain(self, request, context):
            log.info("Metatrainer is invoked")
            metatrainerArgs = {
                'dataset_key': request.dataset_key,
                'meta_features_key': request.meta_features_key,
                'models_key': request.models_key,
                'model_config': pickle.loads(request.model_config)
            }
            result = self.metatrainer.metatrain(metatrainerArgs)

            return stacking_pb2.MetaTrainReply(
                model_full=b'',
                model_full_key=result['model_full_key'],
                meta_predictions=b'',
                meta_predictions_key=result['meta_predictions_key'],
                score=result['score']
            )

if LAMBDA:
    class AWSLambdaMetatrainer:
        def __init__(self, XDTconfig=None):
            self.metatrainer = Metatrainer(XDTconfig)

        def Metatrain(self, event, context):
            log.info("Metatrainer is invoked")
            metatrainerArgs = {
                'dataset_key': event['dataset_key'],
                'meta_features_key': event['meta_features_key'],
                'models_key': event['models_key'],
                'model_config': json.loads(event['model_config'])
            }
            result = self.metatrainer.metatrain(metatrainerArgs)

            return {
                'model_full_key': result['model_full_key'],
                'meta_predictions_key': result['meta_predictions_key'],
                'score': result['score']
            }

def serve():
    transferType = os.getenv('TRANSFER_TYPE', S3)
    if transferType == S3:
        log.info("Using inline or s3 transfers")
        max_workers = int(os.getenv("MAX_SERVER_THREADS", 10))
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        stacking_pb2_grpc.add_MetatrainerServicer_to_server(
            MetatrainerServicer(), server)
        server.add_insecure_port('[::]:' + args.sp)
        server.start()
        server.wait_for_termination()
    elif transferType == XDT:
        log.fatal("XDT not yet supported")
        XDTconfig = XDTutil.loadConfig()
    else:
        log.fatal("Invalid Transfer type")

def lambda_handler(event, context):
    log.basicConfig(level=log.INFO)
    metatrainerServicer = AWSLambdaMetatrainer()
    return metatrainerServicer.Metatrain(event, context)

if not LAMBDA and __name__ == '__main__':
    log.basicConfig(level=log.INFO)
    serve()
