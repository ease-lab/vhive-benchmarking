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

from reducer import Reducer
import tracing

import logging as log
import pickle

LAMBDA = os.environ.get('IS_LAMBDA', 'no').lower() in ['true', 'yes', '1']

if not LAMBDA:
    import grpc
    import argparse
    import boto3
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
    tracing.initTracer("reducer", url=args.zipkinURL)
    tracing.grpcInstrumentClient()
    tracing.grpcInstrumentServer()

INLINE = "INLINE"
S3 = "S3"
XDT = "XDT"

if not LAMBDA:
    class ReducerServicer(stacking_pb2_grpc.ReducerServicer):
        def __init__(self, XDTconfig=None):
            self.reducer = Reducer(XDTconfig)

        def Reduce(self, request, context):
            model_keys, prediction_keys = [], []
            for model_pred_tuple in request.model_pred_tuples:
                model_keys.append(model_pred_tuple.model_key)
                prediction_keys.append(model_pred_tuple.pred_key)

            reducerArgs = {'model_keys': model_keys, 'prediction_keys': prediction_keys}
            response = self.reducer.reduce(reducerArgs)
            return stacking_pb2.ReduceReply(
                models=b'',
                models_key=response['models_key'],
                meta_features=b'',
                meta_features_key=response['meta_features_key']
            )

if LAMBDA:
    class AWSLambdaReducer:
        def __init__(self, XDTconfig=None):
            self.reducer = Reducer(XDTconfig)

        def Reduce(self, event, context):
            mptuples = event['model_pred_tuples'].split(',')
            model_keys, prediction_keys = [], []
            for entry in mptuples:
                tuple = entry.split(':')
                model_keys.append(tuple[0])
                prediction_keys.append(tuple[1])

            reducerArgs = {'model_keys': model_keys, 'prediction_keys': prediction_keys}
            response = self.reducer.reduce(reducerArgs)
            return {'models_key': response['models_key'], 'meta_features_key': response['meta_features_key']}

def serve():
    transferType = os.getenv('TRANSFER_TYPE', S3)
    if transferType == S3:
        log.info("Using inline or s3 transfers")
        max_workers = int(os.getenv("MAX_SERVER_THREADS", 10))
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        stacking_pb2_grpc.add_ReducerServicer_to_server(
            ReducerServicer(), server)
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
    reducerServicer = AWSLambdaReducer()
    return reducerServicer.Reduce(event, context)

if not LAMBDA and __name__ == '__main__':
    log.basicConfig(level=log.INFO)
    serve()
