;; Compare upstream tools.cli behavior to its Basilisp package port.
#?(:clj (load-file "tests/acceptance/upstream/tools-cli/upstream/src/main/clojure/clojure/tools/cli.cljc")
   :lpy (require 'basilisp.tools.cli))

(def parse-opts #?(:clj clojure.tools.cli/parse-opts
                    :lpy basilisp.tools.cli/parse-opts))
(def summarize #?(:clj clojure.tools.cli/summarize
                   :lpy basilisp.tools.cli/summarize))
(def get-default-options #?(:clj clojure.tools.cli/get-default-options
                             :lpy basilisp.tools.cli/get-default-options))

(defn parse-int [value]
  #?(:clj (Integer/parseInt value)
     :lpy (int value)))

(def fuzz-option-specs
  [["-a" "--alpha"]
   ["-b" "--beta"]
   ["-p" "--port PORT"]
   ["-t" "--tag TAG" :multi true]
   ["-v" "--verbose" :default 0 :update-fn inc]
   ["-d" "--[no-]daemon"]])

(def fuzz-tokens
  ["-a" "--alpha" "-b" "--beta" "-p80" "--port=80"
   "-tred" "--tag=blue" "-v" "--verbose" "--daemon" "--no-daemon"
   "file" "--unknown" "--" "-x"])

(defn next-fuzz-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn fuzz-args [case-number]
  (loop [seed (+ 424242 case-number)
         args []
         remaining (+ 1 (mod case-number 9))]
    (if (zero? remaining)
      args
      (let [next-seed (next-fuzz-seed seed)]
        (recur next-seed
               (conj args (nth fuzz-tokens
                               (mod (quot next-seed 65536) (count fuzz-tokens))))
               (dec remaining))))))

(defn fuzz-contract [case-number]
  (let [args (fuzz-args case-number)]
    {:args args
     :result (select-keys (parse-opts args fuzz-option-specs)
                          [:options :arguments :errors])}))

(let [option-specs [["-a" "--alpha"]
                    ["-b" "--beta"]
                    ["-p" "--port PORT" :parse-fn parse-int]
                    ["-v" "--verbose" :default 0 :update-fn inc]
                    ["-d" "--[no-]daemon"]]
      basic (parse-opts ["-abp80" "-v" "--no-daemon"] option-specs)
      strict (parse-opts ["-p" "--alpha"] option-specs :strict true)
      subcommand (parse-opts ["-a" "serve" "-b"] option-specs :subcommand :explicit)
      defaults (get-default-options [["-a" "--alpha" :default true]
                                     ["-b" "--beta" :default 2]
                                     ["-c" "--charlie"]])]
  (println
   (pr-str
    {:basic (select-keys basic [:options :arguments :errors])
     :strict-error? (boolean (:errors strict))
     :subcommand (select-keys subcommand [:options :arguments :errors])
     :defaults defaults
     :fuzz (mapv fuzz-contract (range 256))
     :summary (summarize [{:short-opt "-p"
                           :long-opt "--port"
                           :required "PORT"
                           :default 80
                           :desc "Port"}])})))
