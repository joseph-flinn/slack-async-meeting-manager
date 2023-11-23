with import <nixpkgs> {};
let
  pythonEnv = python311.withPackages(ps: [
    ps.slack-bolt
    ps.python-dotenv

    ps.black
    ps.pytest
  ]);
in mkShell {
  packages = [
    pythonEnv
  ];
}
