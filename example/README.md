This is a working example of a Arc toolbox.
The toolbox can be imported or open in any Arc software, like ArcMap and ArcCatalog (the latter gives you the ability to "check sintax" for errors)

However, to use the toolbox you need to:
 - have arcpy_extender in your path, or
 - manually copy the content of this folder at the same level as the arcpy_extender folder

This is required due to the many limitation of Arc software when trying to manipulate your path within Python, that is the very reason that brought me to develop this library