



"""should be something like


scheduler = Scheduler.init()
random_manager = RandomManager(seed)
model = ChannelModel(params)
topology = Topology(model, random_manager)

context1 = NodeContext(model, CartesianCoordinate(0, 0), scheduler, random_manager)
node1 = topology.spawn_node(id= "something", context1)

context2 = NodeContext(model, CartesianCoordinate(1, 1), scheduler, random_manager)
node2 = topology.spawn_node(id = "somethingelse", context2)


# if you ant to remove a node should be something like
node1.shutdown()  # clean up the node
del context1  # remove the context if needed
topology.remove_node_from_topology(node1.node_id)  # remove the node from the topology


...

"""