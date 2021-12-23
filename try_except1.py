try:
    a, b = input('請輸入二個整數（用空格隔開）：').split()
    a = int(a)
    b = int(b)
    c = a/b
except ZeroDivisionError:
    print("除數不能為零")
except:
    print("錯誤輸入")
else:
    print("答案是 " + str(c))
finally:
    print("程式執行結束")