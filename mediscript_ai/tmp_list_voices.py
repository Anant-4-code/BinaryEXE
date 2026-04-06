import riva.client
import grpc

SERVER = "grpc.nvcf.nvidia.com:443"
FUNCTION_ID = "877104f7-e885-42b9-8de8-f6e4c6303969"
AUTH_TOKEN = "Bearer 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"

def list_voices():
    # Attempting to pass metadata through the gRPC call directly
    auth = riva.client.Auth(uri=SERVER, use_ssl=True)
    service = riva.client.SpeechSynthesisService(auth)
    
    metadata = (
        ('function-id', FUNCTION_ID),
        ('authorization', AUTH_TOKEN)
    )
    
    # Low-level call to the gRPC stub which supports metadata
    print(f"Calling ListVoices on {SERVER} with metadata...")
    from riva.client.proto import riva_tts_pb2
    request = riva_tts_pb2.ListVoicesRequest()
    
    try:
        # service.stub is the Synthesize stub
        # We need the ListVoices stub which might be different or same
        response = service.stub.ListVoices(request, metadata=metadata)
        print(response)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_voices()
    
