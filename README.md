# progressive_randomizer

Tools for progressive randomization

## Examples

### Listing Memory regions

By component

```bash
python -m progressive_randomizer print_component
```

By tag

```bash
python -m progressive_randomizer print_tags
python -m progressive_randomizer print_tags _all
python -m progressive_randomizer print_tags character
```

### Decoding Text

Show decoded battle messages

```bash
python -m progressive_randomizer decode_text bttl_mssgs
```

### Deserializing Memory Regions

```bash
python -m progressive_randomizer deserialize_component bttl_mssgs
python -m progressive_randomizer deserialize_component bttl_mssgs bat_msgs.json
```
