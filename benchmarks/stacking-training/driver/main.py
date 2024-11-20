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

from driver import Driver
import tracing

import logging as log
import pickle

LAMBDA = os.environ.get('IS_LAMBDA', 'no').lower() in ['true', 'yes', '1']

if LAMBDA:
    import boto3
    import json

if not LAMBDA:
    import helloworld_pb2_grpc
    import helloworld_pb2
    import stacking_pb2_grpc
    import stacking_pb2
    import destination as XDTdst
    import source as XDTsrc
    import utils as XDTutil

    import grpc
    from grpc_reflection.v1alpha import reflection
    import argparse
    import socket

    from concurrent import futures

    parser = argparse.ArgumentParser()
    parser.add_argument("-dockerCompose", "--dockerCompose",
        dest="dockerCompose", default=False, help="Env docker compose")
    parser.add_argument("-tAddr", "--tAddr", dest="tAddr",
        default="trainer.default.127.0.0.1.nip.io:80", help="trainer address")
    parser.add_argument("-rAddr", "--rAddr", dest="rAddr",
        default="reducer.default.127.0.0.1.nip.io:80", help="reducer address")
    parser.add_argument("-mAddr", "--mAddr", dest="mAddr",
        default="metatrainer.default.127.0.0.1.nip.io:80", help="metatrainer address")
    parser.add_argument("-trainersNum", "--trainersNum", dest="trainersNum",
        default="3", help="number of training models")
    parser.add_argument("-sp", "--sp", dest="sp", default="80", help="serve port")
    parser.add_argument("-zipkin", "--zipkin", dest="zipkinURL",
        default="http://zipkin.istio-system.svc.cluster.local:9411/api/v2/spans",
        help="Zipkin endpoint url")

    args = parser.parse_args()

if tracing.IsTracingEnabled():
    tracing.initTracer("driver", url=args.zipkinURL)
    tracing.grpcInstrumentClient()
    tracing.grpcInstrumentServer()

INLINE = "INLINE"
S3 = "S3"
XDT = "XDT"

if not LAMBDA:
    class GreeterServicer(helloworld_pb2_grpc.GreeterServicer):
        def __init__(self, XDTconfig=None):
            self.driver = Driver(XDTconfig)

        def train(self, arg: dict) -> dict:
            log.info(f"Invoke Trainer {arg['trainer_id']}")
            channel = grpc.insecure_channel(args.tAddr)
            stub = stacking_pb2_grpc.TrainerStub(channel)

            resp = stub.Train(stacking_pb2.TrainRequest(
                dataset=b'',  # via S3/XDT only
                dataset_key=arg['dataset_key'],
                model_config=pickle.dumps(arg['model_cfg']),
                trainer_id=str(arg['trainer_id'])
            ))

            return {
                'model_key': resp.model_key,
                'pred_key': resp.pred_key
            }

        def reduce(self, training_responses) -> dict:
            log.info("Invoke Reducer")
            channel = grpc.insecure_channel(args.rAddr)
            stub = stacking_pb2_grpc.ReducerStub(channel)

            model_keys = []
            pred_keys = []

            req = stacking_pb2.ReduceRequest()
            for resp in training_responses:
                model_pred_tuple = stacking_pb2.ModelPredTuple()
                model_pred_tuple.model_key = resp['model_key']
                model_pred_tuple.pred_key = resp['pred_key']

                req.model_pred_tuples.append(model_pred_tuple)

            resp = stub.Reduce(req)

            return {
                'meta_features_key': resp.meta_features_key,
                'models_key': resp.models_key
            }

        def train_meta(self, dataset_key: str, reducer_response: dict) -> dict:
            log.info("Invoke MetaTrainer")
            channel = grpc.insecure_channel(args.mAddr)
            stub = stacking_pb2_grpc.MetatrainerStub(channel)

            resp = stub.Metatrain(stacking_pb2.MetaTrainRequest(
                dataset=b'',  # via S3/XDT only
                dataset_key=dataset_key,
                models_key=reducer_response['models_key'],  # via S3 only
                meta_features=b'',
                meta_features_key=reducer_response['meta_features_key'],
                model_config=pickle.dumps(self.driver.modelConfig['meta_model'])
            ))

            return {
                'model_full_key': resp.model_full_key,
                'meta_predictions_key': resp.meta_predictions_key,
                'score': resp.score
            }

        # Driver code below
        def SayHello(self, request, context):
            log.info("Driver received a request")
            dataset_key = self.driver.put_dataset()
            trainingConfig = {
                'num_trainers': int(os.getenv('TrainersNum', args.trainersNum)),
                'concurrent_training': os.getenv('CONCURRENT_TRAINING').lower() in ['true', 'yes', '1'],
                'trainer_function': self.train
            }
            training_responses = self.driver.train_all(dataset_key, trainingConfig)
            reducer_response = self.reduce(training_responses)
            outputs = self.train_meta(dataset_key, reducer_response)
            self.driver.get_final(outputs)
            return helloworld_pb2.HelloReply(message=self.driver.storageBackend.bucket)

if LAMBDA:
    class AWSLambdaServicer():
        def __init__(self, XDTconfig=None):
            self.driver = Driver(XDTconfig)
            self.lambda_client = boto3.client('lambda')

        def train(self, arg: dict) -> dict:
            log.info(f"Invoke Trainer {arg['trainer_id']}")
            arg['model_cfg'] = json.dumps(arg['model_cfg'])
            response = self.lambda_client.invoke(
                FunctionName = os.environ.get('TRAINER_FUNCTION', 'trainer'),
                InvocationType = 'RequestResponse',
                LogType = 'None',
                Payload = json.dumps(arg)
            )
            payloadBytes = response['Payload'].read()
            payloadJson = json.loads(payloadBytes)
            return {
                'model_key': payloadJson['model_key'],
                'pred_key': payloadJson['pred_key']
            }

        def reduce(self, training_responses) -> dict:
            log.info("Invoke Reducer")
            tuples = ['%s:%s' % (t['model_key'], t['pred_key']) for t in training_responses]
            arg = {
                'model_pred_tuples': ','.join(tuples)
            }
            response = self.lambda_client.invoke(
                FunctionName = os.environ.get('REDUCER_FUNCTION', 'reducer'),
                InvocationType = 'RequestResponse',
                LogType = 'None',
                Payload = json.dumps(arg)
            )
            payloadBytes = response['Payload'].read()
            payloadJson = json.loads(payloadBytes)

            return {
                'meta_features_key': payloadJson['meta_features_key'],
                'models_key': payloadJson['models_key']
            }

        def train_meta(self, dataset_key: str, reducer_response: dict) -> dict:
            log.info("Invoke MetaTrainer")
            arg = {
                'dataset_key': dataset_key,
                'models_key': reducer_response['models_key'],
                'meta_features_key': reducer_response['meta_features_key'],
                'model_config': json.dumps(self.driver.modelConfig['meta_model'])
            }
            response = self.lambda_client.invoke(
                FunctionName = os.environ.get('METATRAINER_FUNCTION', 'metatrainer'),
                InvocationType = 'RequestResponse',
                LogType = 'None',
                Payload = json.dumps(arg)
            )
            payloadBytes = response['Payload'].read()
            payloadJson = json.loads(payloadBytes)

            return {
                'model_full_key': payloadJson['model_full_key'],
                'meta_predictions_key': payloadJson['meta_predictions_key'],
                'score': payloadJson['score']
            }

        def SayHello(self, event, context):
            log.info('Driver received a request')
            dataset_key = self.driver.put_dataset()
            trainingConfig = {
                'num_trainers': int(os.getenv('TrainersNum', '4')),
                'concurrent_training': os.getenv('CONCURRENT_TRAINING').lower() in ['true', 'yes', '1'],
                'trainer_function': self.train
            }
            training_responses = self.driver.train_all(dataset_key, trainingConfig)
            reducer_response = self.reduce(training_responses)
            outputs = self.train_meta(dataset_key, reducer_response)
            self.driver.get_final(outputs)
            return self.driver.storageBackend.bucket

def serve():
    transferType = os.getenv('TRANSFER_TYPE', S3)
    if transferType == S3:
        log.info("Using inline or s3 transfers")
        max_workers = int(os.getenv("MAX_SERVER_THREADS", 10))
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        helloworld_pb2_grpc.add_GreeterServicer_to_server(
            GreeterServicer(), server)
        SERVICE_NAMES = (
            helloworld_pb2.DESCRIPTOR.services_by_name['Greeter'].full_name,
            reflection.SERVICE_NAME,
        )
        reflection.enable_server_reflection(SERVICE_NAMES, server)
        server.add_insecure_port('[::]:' + args.sp)
        server.start()
        server.wait_for_termination()
    elif transferType == XDT:
        log.fatal("XDT not yet supported")
    else:
        log.fatal("Invalid Transfer type")

def lambda_handler(event, context):
    log.basicConfig(level=log.INFO)
    lambdaServicer = AWSLambdaServicer()
    return lambdaServicer.SayHello(event, context)

if not LAMBDA and __name__ == '__main__':
    log.basicConfig(level=log.INFO)
    serve()
