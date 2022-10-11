## Obtain airship

Only on world map?

0x1F60 = party xy position
0x1F62 = airship xy position

0x1F62 = 0x1F60

Additionally, in order for it to be visible, need to set flag "The airship is visible"

Cannot enter interior, as no controls available, and Setzer post-opera scene is active, which softlocks without Celes

### WoB with an airship

Can trigger Cyan's introduction at Imperial Camp, Returner's Hideout scene, and Magitek Factory, but Opera / Jidoor is locked out.


## Using the parent map

Setting parent map to 1 from WoB (0) will emerge in WoR, can also set with parent xy position (0x1F6B). You can also set Serpent Trench (2) as the parent map, and you will permanently be in an airship and able to move around (landing automatically puts you back in the airship)

Anything else that's not meant to be a world map freezes upon trying to exit to parent map. I only tried one or two, though, it's possible others could work.

## Changing music

Current song: 0x1F80

### Music player ASM analysis

```asm
LDA $4B                         ; Load cursor slot 
TAX                             ; Index it
LDA $7E9D89,X                   ; Load song ID in slot?
JMP MUSIC_PLAY                  ; Play song

; what's before this in A?
; the song id -- see above
STA $1301    ; store A in $1301 (spc cmd byte 1)
LDA #$10     ; write #10 to A 
STA $1300    ; store A in $1300 (spc cmd byte 0)
LDA #$FF     ; write FF to A
STA $1302    ; store A in $1302 (spc cmd byte 2)   
STZ $1305    ; store 0 in $1305 (current song command byte 1)  
JSL $C50004  ; jump to 0xC50004  
LDY $00      ; write 00 to Y
STY $CF      ; store Y in $CF (why isn't this a STZ?)
STZ $5F      ; store 0 in $5F  
RTS          ; return to caller
```

So, up to the C5 routine call, we have:
```
0x5F: 0x0 (cursor position, unneeded?)
0xCF: 0x0 (frame counter, unneeded?)
; SPC command (play?)
0x130{0,1}: 0x10{songid}
; Volume
0x1302: 0xFF
; set current song
0x1305: 0x0
```

Looks like the C5 function has to be called somehow, though. We can't write to the hardware registers and that appears to be how its triggered.

monitoring

```python
def monitor():
	mem1 = retroarch.RetroArchBridge().read_memory(0x1300, 0x1400)
	iter = 1000000000000
	import time

	while iter > 0:
		print(time.time())
		mem2 = retroarch.RetroArchBridge().read_memory(0x1300, 0x1400)
		frame = [*retroarch.RetroArchBridge().read_memory(0x45, 0x46)][0]
		if mem1 != mem2:
			pprint.pprint([(hex(frame), hex(0x1300 + i), f"{a:02x}", f"{b:02x}") for i, (a, b) in enumerate(zip(mem1, mem2)) if a != b])
			iter = 100
		mem1 = mem2
		iter -= 1
```

## Dialog

0xBA -> 01 will open window with current dialog (if any)

## Events

Monitoring
```python
def monitor():
	mem1 = retroarch.RetroArchBridge().read_memory(0x7E00E5, 0x7E00F0)

	while True:
		mem2 = retroarch.RetroArchBridge().read_memory(0x7E00E5, 0x7E00F0)
		pc, sp, op, data = mem2[:3], mem2[3:5], mem2[5:6], mem2[6:]
		if mem1 != mem2:
			print(mem2)
			print(pc, sp, op, data)
		mem1 = mem2
```

```
 ++ $E5 Event PC
  + $E8 Event Stack Pointer
    $EA Event Op Code
$EB-$EF Event Code Data (up to 5)
```

### recovery spring

0xE5 - 0xF0
```
b'\xae 3   \xcc | \x03\x00 | \xff | I \xfe \xb2 3 ^'
b'\x00 \x00\xca | \x00\x00 | \xff | I \xfe \xb2 3 ^'
```

### dialog

second after first button to open
third after second button to close
```
b'\xaa 3   \xcc | \x03\x00 | \xff | I    \xfe \xb2 3 ^'
b'\x01 \x00\xca | \x06\x00 | I    | \xfe \xb2 3    ^ \x00'
b'\x00 \x00\xca | \x00\x00 | \xff | I    \xfe \xb2 3 ^'
```

### map transition

Nothing happens on map transition

### checking item pot

second after first button to open
third after second button to close
```
# puts item in inventory? --- doesn't appear so...
b'\x08\x00\xca | \x03\x00 | \xff  | I    \xfe \xb2 3 ^'
# This must be the dialog open command
b'\x01\x00\xca | \x06\x00 | I     | \xfe \xb2 3    ^ \x00'
# This must return control to player
b'\x00\x00\xca | \x00\x00 | \xff  | I    \xfe \xb2 3 ^'
```

### MIAB

```
b'@\x00\xca    | \x03\x00 | \xff | I\xfe\xb23^'
b'\x01\x00\xca | \x06\x00 | I    | \xfe\xb23^\x00'
# Delay here
b',\x0e\xcb    | \x06\x00 | \x04 | \x82\xd7\xff\xfe1'
```

### Entering Returner's Hideout for First Time

Music changes on entering door

```
# F0 is a music change
# 0x2E is the song id, FE is fixed
b'_\xf9\xca'    | b'\x06\x00' | b'\xf0' | b'.\xfeK"\x01'
# Return to normal
b'\x00\x00\xca' | b'\x00\x00' | b'\xff' | b'I\xfe\xb23^'
# exit cave - F0 is another music change
b'K\xf9\xca'    | b'\x06\x00' | b'\xf0' | b'\x06\xfe\xc0\xb6\x81'
```

General actions in https://www.ff6hacking.com/wiki/doku.php?id=ff3:ff3us:doc:asm:codes:event_codes
Field events in https://www.ff6hacking.com/wiki/doku.php?id=ff3:ff3us:doc:asm:rom_map:field_events

The game seems to constantly overwrite 0xEA when its in its idle loop
We can overwrite the script PC pointer with where we want it to go, but it often will crash the game afterwards
The trick might be in what comes after the "arguments" in the final piece or the stack pointer values
