import uuid

# Generate a random UUID
def unique_id() -> str:
   my_uuid = uuid.uuid4()
   return my_uuid.hex
