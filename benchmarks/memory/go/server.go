// MIT License

// Copyright (c) 2022 EASE lab

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

// Package main implements a server for Aes service.
package main

import (
	"context"
	"flag"
	"fmt"
	"net"
	"time"
	"math/rand"

	log "github.com/sirupsen/logrus"
	pb "github.com/vhive-serverless/vSwarm-proto/proto/aes"
	tracing "github.com/vhive-serverless/vSwarm/utils/tracing/go"

	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
)

var (
	zipkin                    = flag.String("zipkin", "http://localhost:9411/api/v2/spans", "zipkin url")
	address                   = flag.String("addr", "0.0.0.0:50051", "Address:Port the grpc server is listening to")
	key_string                = flag.String("key", "6368616e676520746869732070617373", "The key which is used for encryption")
	default_plaintext_message = flag.String("default-plaintext", "defaultplaintext", "Default plaintext when the function is called with the plaintext_message world")
)

const (
	arraySize   = 1 // in megabytes
	numAccesses = 1000
	sleepDuration = time.Microsecond * time.Duration(1)
)

// server is used to implement aes.AesServer.
type server struct {
	pb.UnimplementedAesServer
}


// ShowEncryption implements aes.AesServer
func (s *server) ShowEncryption(ctx context.Context, in *pb.PlainTextMessage) (*pb.ReturnEncryptionInfo, error) {
	// Seed the random number generator
	startTime := time.Now()
	rand.Seed(time.Now().UnixNano())

	// Create a large byte slice
	data := make([]byte, arraySize*1024*1024)

	// Perform random accesses
	for i := 0; i < numAccesses; i++ {
		randomIndex := rand.Intn(arraySize)
		data[randomIndex] += 1 // Modify the value to ensure the memory access is not optimized away
		time.Sleep(sleepDuration)
	}
	elapsedTime := time.Since(startTime)
	return &pb.ReturnEncryptionInfo{EncryptionInfo: fmt.Sprintf("%s", elapsedTime)}, nil
}

func main() {
	flag.Parse()
	if tracing.IsTracingEnabled() {
		log.Printf("Start tracing on : %s\n", *zipkin)
		shutdown, err := tracing.InitBasicTracer(*zipkin, "memory function")
		if err != nil {
			log.Warn(err)
		}
		defer shutdown()
	}

	lis, err := net.Listen("tcp", *address)
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	log.Printf("Start MEMORY-go server. Addr: %s\n", *address)

	var grpcServer *grpc.Server
	if tracing.IsTracingEnabled() {
		grpcServer = tracing.GetGRPCServerWithUnaryInterceptor()
	} else {
		grpcServer = grpc.NewServer()
	}
	pb.RegisterAesServer(grpcServer, &server{})
	reflection.Register(grpcServer)

	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
