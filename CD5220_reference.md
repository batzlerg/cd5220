# Technical Reference for CD5220 Command Set

This guide covers the PTC (Partner Tech Corp) standard command set for the CD5220 VFD customer display, focusing on practical point-of-sale (POS) usage patterns. All commands are sent as hexadecimal byte sequences over an RS-232 serial connection, typically set to 9600 baud, N, 8, 1.

Its primary and only source is the [User's Manual for the CD5220 display](https://cdn.barcodesinc.com/resources/CD5220_Manual.pdf).

### Initialization and Screen Management

These fundamental commands control the display's state, preparing it for new information or clearing it between transactions.

**Initialize Display**

* **Command:** `ESC @`
* **Hex Sequence:** `1B 40`
* **Description:** This is the most crucial command for starting a session. It performs a soft reset of the display, clearing the screen, moving the cursor to the home position (top-left, 1,1), setting brightness to default, and canceling any special modes like scrolling or user-defined characters. It ensures the display is in a known, default state.
* **POS Usage Example:** A POS terminal should send this command immediately upon establishing a connection with the display to guarantee a clean start before the first transaction of the day.
    * **Sequence:** `[1B] `

**Clear Screen**

* **Command:** `CLR`
* **Hex Sequence:** `0C`
* **Description:** This command erases all 40 characters from both lines of the display and returns the cursor to the home position. It is also used to terminate the restrictive "string display mode" initiated by `ESC Q A` or `ESC Q B`.
* **POS Usage Example:** This command is typically sent at the end of a customer transaction to clear the final total and payment confirmation, preparing the display for the next customer.
    * **Sequence:** `[0C]`

**Clear Cursor Line**

* **Command:** `CAN`
* **Hex Sequence:** `18`
* **Description:** Wipes all characters from the line the cursor is currently on. Like `CLR`, this also deactivates string display modes.
* **POS Usage Example:** If a cashier voids the last scanned item, this command can be used to clear just that item's line without affecting the rest of the transaction details on the other line.
    * **Scenario:** The display shows "Milk......\$3.50" on line 1 and "Bread.....\$2.25" on line 2. The cursor is on line 2.
    * **Sequence:** ``
    * **Result:** Line 2 is cleared, while line 1 remains unchanged.


### Display Modes

These commands dictate how text behaves when it is written to the display.

**Overwrite Mode (Default)**

* **Command:** `ESC DC1`
* **Hex Sequence:** `1B 11`
* **Description:** In this mode, new characters replace any existing characters at the cursor's position. The cursor then automatically advances. This is the standard mode for most POS operations.
* **POS Usage Example:** Displaying an item and its price.

1. Send `"Milk      "` (10 characters)
2. Send `"$3.99"`
    * **Result:** `Milk      $3.99`

3. Move cursor to home (`0B`)
4. Send `"Bread     "`
    * **Result:** `Bread     $3.99` (The word "Milk" is overwritten)

**Vertical Scroll Mode**

* **Command:** `ESC DC2`
* **Hex Sequence:** `1B 12`
* **Description:** When text is written past the end of the bottom line, the content of the top line is discarded, the bottom line's content moves up to the top line, and the new text appears on the now-empty bottom line. This creates a "ticker tape" effect.
* **POS Usage Example:** Displaying a running list of scanned items in a transaction.

1. Activate mode: `[1B] `
2. Send: `"Item 1             "`
3. Send: `"Item 2             "`
4. Send: `"Item 3             "`
    * **Result:** As "Item 3" is written, "Item 1" scrolls off the top of the screen, and "Item 2" moves to the top line.

**Horizontal Scroll Mode**

* **Command:** `ESC DC3`
* **Hex Sequence:** `1B 13`
* **Description:** In this mode, the cursor is hidden. Characters are pushed onto the display from the right, causing existing text to shift left one position at a time. This is ideal for messages longer than 20 characters.
* **POS Usage Example:** Displaying a promotional message when the terminal is idle.

1. Activate mode: `[1B] `
2. Send the message: `"Visit our deli for weekly specials! "`
    * **Result:** The message will continuously scroll across the top line of the display.


### Cursor Control and Positioning

These commands give you precise control over where the next character will be written.


| Function | Command | Hex Sequence | POS Usage Scenario |
| :-- | :-- | :-- | :-- |
| **Move to Home** | `HOM` or `ESC [ H` | `0B` or `1B 5B 48` | Start writing at the top-left corner. Used before displaying the first item. |
| **Move to Start of Line** | `CR` or `ESC [ L` | `0D` or `1B 5B 4C` | After writing a line, return to the beginning of the same line to overwrite it. |
| **Move Down One Line** | `LF` or `ESC [ B` | `0A` or `1B 5B 42` | Move from the item line (top) to the total/payment line (bottom). |
| **Move to Bottom-Left** | `ESC [ K` | `1B 5B 4B` | Immediately jump to the start of the second line to display a total. |

**Move to Specific Position**

* **Command:** `ESC l x y`
* **Hex Sequence:** `1B 6C <x> <y>` where `x` is column (1-20) and `y` is row (1-2).
* **Description:** Moves the cursor to an absolute coordinate on the display.
* **POS Usage Example:** To create a neatly formatted price display.

1. `[0C]` (Clear screen)
2. Send `TOTAL DUE`
3. Move cursor to column 1, row 2: `[1B] [6C]  `
4. Send `$24.50`
    * **Result:**

```
TOTAL DUE
$24.50
```


**Set Cursor Visibility**

* **Command:** `ESC _ n`
* **Hex Sequence:** `1B 5F <n>` where `n` is `0` for OFF or `1` for ON.
* **Description:** Toggles the blinking block cursor.
* **POS Usage Example:** Turn the cursor off (`1B 5F 00`) for a cleaner, more professional final display of the total price. Turn it on (`1B 5F 01`) while an operator is inputting data.


### Specialized String Display

These commands write an entire line at once but have unique behavior.

* **Write to Upper/Lower Line:** `ESC Q A/B <string> CR` (`1B 51 41/42 ... 0D`)
    * **Description:** Writes a string of up to 20 characters to the specified line. **Crucially, after using this command, the display enters a locked mode where most other commands are ignored.** The display must be cleared with `CLR` (0C) or `CAN` (0x18) to resume normal operation.
    * **POS Usage Example:** Displaying fixed headers.

1. `[1B]  ` + `ITEM                ` + `[0D]`
2. `[1B]  ` + `PRICE               ` + `[0D]`
        * **Result:** The display is now locked, showing "ITEM" and "PRICE" headers. You must send `[0C]` to unlock it and display transaction data.
* **Continuously Scroll Upper Line:** `ESC Q D <string> CR` (`1B 51 44 ... 0D`)
    * **Description:** Scrolls a message (up to 40 characters) on the top line. The scrolling continues until *any* other command is received, which will then stop the scroll, clear the line, and move the cursor to the home position.
    * **POS Usage Example:** Displaying a welcome message during idle periods.

1. Send `[1B]  ` + `"Welcome to our store! "` + `[0D]`
        * The message scrolls until the cashier starts a new transaction, sending a `CLR` command which stops the scroll and prepares the display.


### Advanced and Utility Commands

These commands control hardware features and character sets.

**Brightness Adjustment**

* **Command:** `ESC * n`
* **Hex Sequence:** `1B 2A <n>` where `n` is 1 (25%), 2 (50%), 3 (75%), or 4 (100%).
* **Description:** Sets the VFD tube brightness.
* **POS Usage Example:** A settings menu in the POS software could allow a manager to set the brightness to level 2 (`1B 2A 02`) to save power or reduce glare in a dimly lit environment.

**Select International Character Set**

* **Command:** `ESC f n`
* **Hex Sequence:** `1B 66 <n>` where `n` is an ASCII character representing the country (e.g., `G` for Germany, `F` for France).
* **Description:** Switches the character map to support different languages and currency symbols.
* **POS Usage Example:** For a POS system in Quebec, send `1B 66 46` (`F` for France) to access characters like 'é' and 'ç'.

**User-Defined Characters**

* **Commands:**
    * **Define:** `ESC & 1 n m [data]` (`1B 26 01 <n> <m> ...`)
    * **Select/Cancel:** `ESC %` (`1B 25`)
    * **Delete:** `ESC ?` (`1B 3F`)
    * **Save to EEPROM:** `ESC s 1` (`1B 73 01`)
* **Description:** This feature allows you to create custom 5x7 dot matrix characters. You send the definition command followed by 5 bytes for each character, representing the pixel pattern for each row. `ESC %` toggles between the standard and user-defined sets.
* **POS Usage Example:** A coffee shop wants a custom "cup" symbol (☕).

1. The POS application defines the symbol at character code `0x80` by sending `1B 26 01 80 80 [5 bytes of pixel data]`.
2. The definition is saved permanently: `[1B]  `.
3. To display it: `[1B] ` (select user set), send ``, then `[1B] ` again to switch back to the standard set for text.
