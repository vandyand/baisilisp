;; Primitive array cases compare data-only views of Clojure JVM arrays and the
;; Python-hosted Basilisp representations.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

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
