# Or a number of its own

Instead of linking this computer to your own Signal, Halo can have a number of its own -- a spare SIM or a VoIP
number that receives an SMS or a call. Then you text Halo like a contact, and more than one phone can pair with it.

In a Halo session (or `bin/signal.py ctl` in the pack's folder):

```
/signal register +15550100
```

Signal asks for a captcha first: open https://signalcaptchas.org/registration/generate.html in a browser, solve it,
copy the link behind "Open Signal" (it starts with `signalcaptcha://`), and run:

```
/signal register +15550100 --captcha signalcaptcha://...
/signal register +15550100 --code 123456
```

`--voice` asks for a call instead of an SMS (after an SMS was asked for once); `--pin <pin>` when the number already
has a registration lock. Halo sets a registration-lock PIN of its own and keeps it in the pack's data folder (0600).
`/signal url` then shows the link and QR code that open the chat with that number on your phone.
