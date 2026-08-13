package dev.p2pkit.build;

import org.gradle.api.publish.maven.MavenPom;

/** Applies the repository-wide Maven Central identity to a publication POM. */
public final class P2pPomMetadata {
    private static final String REPOSITORY_URL = "https://github.com/p2pKit/P2pKit";

    private P2pPomMetadata() {
    }

    public static void configure(MavenPom pom) {
        pom.getUrl().set(REPOSITORY_URL);
        pom.licenses(licenses -> licenses.license(license -> {
            license.getName().set("The Apache License, Version 2.0");
            license.getUrl().set("https://www.apache.org/licenses/LICENSE-2.0.txt");
        }));
        pom.developers(developers -> developers.developer(developer -> {
            developer.getId().set("Apdelrahman1911");
            developer.getName().set("Abdelrahman");
            developer.getEmail().set("apdelrahman1911@users.noreply.github.com");
            developer.getOrganization().set("p2pKit");
            developer.getOrganizationUrl().set("https://github.com/p2pKit");
        }));
        pom.scm(scm -> {
            scm.getUrl().set(REPOSITORY_URL);
            scm.getConnection().set("scm:git:https://github.com/p2pKit/P2pKit.git");
            scm.getDeveloperConnection().set("scm:git:ssh://git@github.com/p2pKit/P2pKit.git");
        });
    }
}
