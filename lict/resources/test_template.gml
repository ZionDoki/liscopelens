graph [
  directed 1
  multigraph 1
  node [
    id 0
    label "root_node"
    parser_name "TestParser"
    type "executable"
  ]
  node [
    id 1
    label "node1"
    parser_name "TestParser"
    type "shared_library"
  ]
  node [
    id 2
    label "node2"
    parser_name "TestParser"
    type "shared_library"
  ]
  node [
    id 3
    label "node3"
    parser_name "TestParser"
    type "code"
  ]
  node [
    id 4
    label "node4"
    parser_name "TestParser"
    type "code"
  ]
  node [
    id 5
    label "node5"
    parser_name "TestParser"
    type "code"
  ]
  node [
    id 6
    label "node6"
    parser_name "TestParser"
    type "code"
  ]
  edge [
    source 0
    target 1
    key 0
    parser_name "TestParser"
    label "deps"
  ]
  edge [
    source 0
    target 2
    key 0
    parser_name "TestParser"
    label "deps"
  ]
  edge [
    source 1
    target 3
    key 0
    parser_name "TestParser"
    label "sources"
  ]
  edge [
    source 1
    target 4
    key 0
    parser_name "TestParser"
    label "sources"
  ]
  edge [
    source 2
    target 5
    key 0
    parser_name "TestParser"
    label "sources"
  ]
  edge [
    source 2
    target 6
    key 0
    parser_name "TestParser"
    label "sources"
  ]
]
