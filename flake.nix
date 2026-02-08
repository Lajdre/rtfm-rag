{
  description = "FHS compatible environment for Crawl4AI";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in
    {
      defaultPackage = self.fhsCrawl4ai;

      fhsCrawl4ai = pkgs.buildFHSEnv {
        name = "crawl4ai-fhs";
        targetPkgs = pkgs: [
          pkgs.nodejs
          pkgs.curl
        ];
        runScript = ''
          bash -c 'crawl4ai-setup && $PYTHONPATH -m playwright install --with-deps && crwl "$@"' -- "$@"
        '';
      };
    };
}
