;; Primitive array cases compare data-only views of Clojure JVM arrays and the
;; Python-hosted Basilisp representations.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(emit-case :defaults
           {:boolean (vec (boolean-array 3))
            :byte    (vec (byte-array 3))
            :char    (vec (char-array 3))
            :short   (vec (short-array 3))
            :int     (vec (int-array 3))
            :long    (vec (long-array 3))
            :float   (vec (float-array 3))
            :double  (vec (double-array 3))})

(emit-case :sources-and-partial-fill
           {:boolean (vec (boolean-array [true false true]))
            :byte    (vec (byte-array [-1 0 127]))
            :char    (vec (char-array "aZ"))
            :short   (vec (short-array 4 [-1 2]))
            :int     (vec (int-array 4 [1 2]))
            :long    (vec (long-array 3 42))
            :float   (vec (float-array [1 2.5]))
            :double  (vec (double-array [1 2.5]))})

(emit-case :fixed-width-coercion
           {:byte  (vec (byte-array [128 -129]))
            :short (vec (short-array [32768 -32769]))
            :int   (vec (int-array [2147483648 -2147483649]))
            :long  (vec (long-array [9223372036854775808 -9223372036854775809]))
            :float (vec (float-array [16777217]))})

(let [bytes (byte-array [0])
      ints  (int-array [0])
      chars (char-array [\a])
      clone (aclone ints)]
  (aset-byte bytes 0 -1)
  (aset-int ints 0 -1)
  (aset-char chars 0 \Z)
  (aset-int clone 0 7)
  (emit-case :mutation-and-clone
             {:byte (vec bytes)
              :int (vec ints)
              :char (vec chars)
              :clone (vec clone)
              :original (vec ints)}))

(emit-case :primitive-array-casts
           {:boolean (vec (booleans (boolean-array [true false])))
            :byte    (vec (bytes (byte-array [-1 0 127])))
            :char    (vec (chars (char-array "aZ")))
            :short   (vec (shorts (short-array [-1 2])))
            :int     (vec (ints (int-array [1 2])))
            :long    (vec (longs (long-array [1 2])))
            :float   (vec (floats (float-array [1 2.5])))
            :double  (vec (doubles (double-array [1 2.5])))})

(emit-case :primitive-array-cast-rejections
           {:boolean (rejected? #(booleans 3))
            :byte    (rejected? #(bytes [1 2]))
            :char    (rejected? #(chars "az"))
            :short   (rejected? #(shorts (int-array [1])))
            :int     (rejected? #(ints (long-array [1])))
            :long    (rejected? #(longs (int-array [1])))
            :float   (rejected? #(floats (double-array [1.0])))
            :double  (rejected? #(doubles (float-array [1.0])))})

(let [nested (object-array [(byte-array [1 2])
                            (int-array [3 4])])]
  (emit-case :indexed-access-and-length
             {:lengths [(alength (boolean-array 3))
                        (alength (byte-array [1 2]))
                        (alength (char-array "aZ"))
                        (alength (short-array [1 2 3]))
                        (alength (int-array [1]))
                        (alength (long-array [1 2]))
                        (alength (float-array [1 2 3 4]))
                        (alength (double-array [1 2 3]))]
              :values [(aget (byte-array [-1 0 127]) 0)
                       (aget (char-array "aZ") 1)
                       (aget (int-array [1 2 3]) 2)
                       (aget nested 0 1)
                       (aget nested 1 0)]}))

(let [booleans (boolean-array [false])
      bytes    (byte-array [0])
      chars    (char-array [\a])
      shorts   (short-array [0])
      ints     (int-array [0])
      longs    (long-array [0])
      floats   (float-array [0])
      doubles  (double-array [0])
      returns  [(aset-boolean booleans 0 true)
                (aset-byte bytes 0 -1)
                (aset-char chars 0 \Z)
                (aset-short shorts 0 -2)
                (aset-int ints 0 -3)
                (aset-long longs 0 -4)
                (aset-float floats 0 1.25)
                (aset-double doubles 0 2.5)]]
  (emit-case :typed-aset-helpers
             {:returns returns
              :values {:boolean (vec booleans)
                       :byte (vec bytes)
                       :char (vec chars)
                       :short (vec shorts)
                       :int (vec ints)
                       :long (vec longs)
                       :float (vec floats)
                       :double (vec doubles)}}))

(let [direct (object-array [:a :b :c])
      nested (object-array [(object-array [:x])])
      returns [(aset direct 1 :changed)
               (aset nested 0 0 :nested)]]
  (emit-case :generic-aset-helper
             {:returns returns
              :direct (vec direct)
              :nested (vec (aget nested 0))}))

(let [values (int-array [1 2 3 4])]
  (emit-case :array-macro-helpers
             {:amap (vec (amap values idx ret (+ idx (aget ret idx))))
              :areduce (areduce values idx ret 0 (+ ret (aget values idx)))
              :empty-amap (vec (amap (int-array 0) idx ret (+ idx (aget ret idx))))
              :empty-areduce (areduce (int-array 0) idx ret 42
                                      (+ ret (aget values idx)))}))
