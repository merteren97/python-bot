# test_interception_z.py
# Gereksinim: Interception driver kurulu ve python paket yüklü. Script'i admin olarak çalıştır.
import time
try:
    import interception   # interception-python / pyinterception
except Exception as e:
    print("interception modülü import edilemedi:", e)
    raise SystemExit(1)

# auto-capture (pyinterception README örneklerinden)
interception.auto_capture_devices()

print("Interception ile 'z' gönderiliyor (200 ms aralık). Ctrl+C ile durdur.")
try:
    while True:
        interception.press('z')   # pyinterception yüksek seviye API örneği
        print("pressed z")
        time.sleep(0.2)
except KeyboardInterrupt:
    print("Durduruldu.")
