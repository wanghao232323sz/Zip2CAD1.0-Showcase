# Zip2CAD Public Task Models v1

The author releases the project-specific task-head weights in this directory under the MIT license (see [LICENSE](LICENSE)). This release does not include or relicense the ZipMap, Sonata, or MobileSAM backbones; obtain their weights from the respective official sources.

| File | Architecture and Purpose | Training Record |
|---|---|---|
| `semantic.pt` | GraphRoofHead over frozen 1,088-dimensional Sonata features; nine semantic classes; includes feature mean and standard deviation | `graph_boundary_facade`, 1,500 steps |
| `geometry.pt` | Separate room and duct branches; 25 output parameters; preserves the room branch weights | Combines trained branches with 7,500 effective steps each for room and ducts; combining them adds no training |
| `corners.pt` | PointNet attention head with 44,440 parameters; six fixed corner roles, ABCDEF | 3,000 cumulative steps, `metric_edges_v2` |

Model tensors are identical to the local trained versions. The semantic checkpoint removes only optimizer state, random state, and training logs while retaining the normalization required for inference. See [manifest.json](manifest.json) for SHA256 checksums and source-checkpoint hashes. Inference does not load the original reference SKP.

Training uses real ZipMap observations from a single library, verified supervision, and some procedural augmentation. There is no generalization evaluation on independent buildings. The geometry head supports only one room and two ducts, each with three nodes. The corner head depends on its six fixed roles and coordinate contract. The models may retain shape priors from the training building, so performance on unfamiliar buildings is not guaranteed. Synthetic forward passes must not be presented as accuracy validation.

See [using public models](../../docs/USE_PRETRAINED.md) for research usage. Original campus training CAD, raw training data, and the full hybrid research case are excluded from the source repository, so complete reproduction from those original data is not provided.

For the prepared live demonstration, see the [project README](../../README.md). The separately distributed `Zip2CAD1.0-Showcase-library-demo.zip` supplies saved observation inputs and demonstration SKP files. The Showcase reruns the geometry and corner heads without training. Its prepared full-campus deliverable is a separate presentation artifact, not a campus model generated live by these heads.
