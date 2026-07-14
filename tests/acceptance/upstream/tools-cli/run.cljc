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
     :summary (summarize [{:short-opt "-p"
                           :long-opt "--port"
                           :required "PORT"
                           :default 80
                           :desc "Port"}])})))
