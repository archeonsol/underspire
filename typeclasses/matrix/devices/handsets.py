
from typeclasses.matrix.objects import NetworkedObject
from typeclasses.items import Item

class Handset(NetworkedObject, Item) :
  """
  Matrix handset thing. This will have its own ID and act as a device on its own.
  However for interactions many verbs will wind up using the ID of the person rather
  than the ID of this device (unless it's jailbroken and then it'll use the device ID)
  """
  set_matrix_user_alias(MatrixId, NewAlias) :
    pass

  get_matrix_user_alias(MatrixId) :
    pass
